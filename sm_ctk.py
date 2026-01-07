import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

import subprocess
import json
import os
import sys
import shutil
import threading
import queue


class ServiceManagerApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("Fedora Pro Manager (Stable)")
        self.root.geometry("1000x720")
        self.root.minsize(820, 620)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # State
        self.commands_path = self.get_commands_path()
        self.commands_data = {"commands": []}
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self.selected_cmd_index: int | None = None
        self.cmd_row_buttons: list[ctk.CTkButton] = []

        # UI
        self.setup_ui()
        self.reload_commands()

        # Process log queue
        self.root.after(80, self.process_queue)

    # -------------------------
    # Persistence (per-user for builds)
    # -------------------------
    def get_commands_path(self) -> str:
        """Return a writable per-user commands.json path.

        - In PyInstaller onefile builds, bundled data lives in a temp dir (sys._MEIPASS)
          and should not be written.
        - For dev runs, we prefer the local commands.json next to the script.
        """

        def resource_path(rel_path: str) -> str:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base, rel_path)

        app_dir_name = "Service-APP-GUI"

        # If frozen (built), always use per-user config
        if getattr(sys, "frozen", False):
            xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
            if not xdg_config_home:
                xdg_config_home = os.path.join(os.path.expanduser("~"), ".config")
            config_dir = os.path.join(xdg_config_home, app_dir_name)
            os.makedirs(config_dir, exist_ok=True)
            target = os.path.join(config_dir, "commands.json")
            self.ensure_commands_file(target, resource_path("commands.json"))
            return target

        # Dev: next to script if possible
        script_dir = os.path.dirname(os.path.abspath(__file__))
        target = os.path.join(script_dir, "commands.json")
        self.ensure_commands_file(target, target)
        return target

    def ensure_commands_file(self, target_path: str, template_path: str) -> None:
        if os.path.exists(target_path):
            return
        try:
            if os.path.exists(template_path):
                os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
                shutil.copyfile(template_path, target_path)
                return
        except Exception:
            pass

        try:
            os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump({"commands": []}, f, ensure_ascii=False, indent=4)
                f.write("\n")
        except Exception:
            pass

    def load_commands_from_disk(self) -> None:
        if not os.path.exists(self.commands_path):
            raise FileNotFoundError(f"commands.json not found at {self.commands_path}")
        with open(self.commands_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "commands" not in data or not isinstance(data.get("commands"), list):
            raise ValueError("Invalid commands.json format. Expected { 'commands': [ ... ] }")

        normalized: list[dict[str, str]] = []
        for item in data.get("commands", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            cmd = str(item.get("command", "")).strip()
            if not name or not cmd:
                continue
            normalized.append({"name": name, "command": cmd})

        self.commands_data = {"commands": normalized}

    def save_commands_to_disk(self) -> None:
        with open(self.commands_path, "w", encoding="utf-8") as f:
            json.dump(self.commands_data, f, ensure_ascii=False, indent=4)
            f.write("\n")

    # -------------------------
    # UI helpers
    # -------------------------
    def setup_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self.root)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 10))
        header.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(header, text="FEDORA MANAGER PRO", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=12, pady=10)

        subtitle = ctk.CTkLabel(header, text="System Control • Command Launcher", text_color=("#6b7280", "#a3b2d6"))
        subtitle.grid(row=0, column=1, sticky="e", padx=12)

        self.btn_exit = ctk.CTkButton(header, text="Exit", fg_color="#ef4444", hover_color="#dc2626", command=self.on_exit, width=90)
        self.btn_exit.grid(row=0, column=2, sticky="e", padx=(0, 12))

        # Body
        body = ctk.CTkFrame(self.root)
        body.grid(row=1, column=0, sticky="nsew", padx=14)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: categories + commands
        self.left_container = ctk.CTkFrame(body)
        self.left_container.grid(row=0, column=0, sticky="nsw", padx=(0, 12), pady=12)
        self.left_container.grid_rowconfigure(0, weight=1)
        self.left_container.grid_columnconfigure(0, weight=1)

        # Recreated on refresh
        self.left_tabs: ctk.CTkTabview | None = None

        # Right: manual command + log
        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="nsew", pady=12)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        manual = ctk.CTkFrame(right)
        manual.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 10))
        manual.grid_columnconfigure(0, weight=1)

        self.manual_entry = ctk.CTkEntry(manual, placeholder_text="Run command... (type 'clear' to clear log)")
        self.manual_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.manual_entry.bind("<Return>", lambda e: self.on_run_manual_command())

        self.manual_run_btn = ctk.CTkButton(manual, text="Run", command=self.on_run_manual_command, width=100)
        self.manual_run_btn.grid(row=0, column=1, sticky="e")

        self.log_text = ctk.CTkTextbox(right)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # Setup tags on underlying tk.Text
        self._log_tk = self.log_text._textbox
        self._log_tk.configure(state="disabled")
        self._log_tk.tag_config("info", foreground="#9fb2d6")
        self._log_tk.tag_config("success", foreground="#22c55e")
        self._log_tk.tag_config("error", foreground="#ef4444")

        # Command Manager
        manager = ctk.CTkFrame(self.root)
        manager.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 14))
        manager.grid_columnconfigure(1, weight=1)

        manager_title = ctk.CTkLabel(manager, text="Command Manager", font=ctk.CTkFont(size=14, weight="bold"))
        manager_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))

        # Left list
        self.cmd_list = ctk.CTkScrollableFrame(manager, height=160)
        self.cmd_list.grid(row=1, column=0, sticky="nsew", padx=(12, 10), pady=(0, 12))

        # Right form
        form = ctk.CTkFrame(manager)
        form.grid(row=1, column=1, sticky="nsew", padx=(0, 12), pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Category").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.category_combo = ctk.CTkComboBox(form, values=["General"], width=220)
        self.category_combo.grid(row=0, column=1, sticky="w", padx=12, pady=(12, 6))
        self.category_combo.set("General")

        ctk.CTkLabel(form, text="Name").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 6))
        self.name_entry = ctk.CTkEntry(form)
        self.name_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 6))

        ctk.CTkLabel(form, text="Command").grid(row=2, column=0, sticky="nw", padx=12, pady=(0, 6))
        self.cmd_text = ctk.CTkTextbox(form, height=70)
        self.cmd_text.grid(row=2, column=1, sticky="ew", padx=12, pady=(0, 8))

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 12))

        self.btn_new = ctk.CTkButton(actions, text="New", width=90, command=self.on_new_command, fg_color="#334155")
        self.btn_new.grid(row=0, column=0, padx=(0, 8))

        self.btn_add = ctk.CTkButton(actions, text="Add", width=90, command=self.on_add_command)
        self.btn_add.grid(row=0, column=1, padx=(0, 8))

        self.btn_update = ctk.CTkButton(actions, text="Update", width=90, command=self.on_update_command, fg_color="#22c55e", hover_color="#16a34a", text_color="#052e12")
        self.btn_update.grid(row=0, column=2, padx=(0, 8))

        self.btn_delete = ctk.CTkButton(actions, text="Delete", width=90, command=self.on_delete_command, fg_color="#ef4444", hover_color="#dc2626")
        self.btn_delete.grid(row=0, column=3, padx=(0, 8))

        self.btn_save = ctk.CTkButton(actions, text="Save", width=90, command=self.on_save_commands)
        self.btn_save.grid(row=0, column=4, padx=(0, 8))

        self.btn_reload = ctk.CTkButton(actions, text="Reload", width=90, command=self.on_reload_commands, fg_color="#334155")
        self.btn_reload.grid(row=0, column=5)

    def _category_from_name(self, name: str) -> str:
        if not isinstance(name, str):
            return "General"
        if ":" in name:
            prefix = name.split(":", 1)[0].strip()
            return prefix or "General"
        return "General"

    def _split_name(self, full_name: str) -> tuple[str, str]:
        if isinstance(full_name, str) and ":" in full_name:
            cat, rest = full_name.split(":", 1)
            cat = (cat or "").strip() or "General"
            rest = (rest or "").strip()
            return cat, rest
        return "General", str(full_name or "").strip()

    def _build_full_name(self, category: str, name: str) -> str:
        category = (category or "").strip() or "General"
        name = (name or "").strip()
        if category.lower() == "general":
            return name
        return f"{category}: {name}"

    # -------------------------
    # Refresh UI from data
    # -------------------------
    def reload_commands(self) -> None:
        try:
            self.load_commands_from_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load commands.json:\n{e}")
            self.commands_data = {"commands": []}

        self.refresh_left_tabs()
        self.refresh_command_manager_list()
        self.refresh_category_options()

    def refresh_left_tabs(self) -> None:
        # Recreate tabs to simplify refresh
        if self.left_tabs is not None:
            try:
                self.left_tabs.destroy()
            except Exception:
                pass

        self.left_tabs = ctk.CTkTabview(self.left_container, width=300)
        self.left_tabs.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        grouped: dict[str, list[tuple[str, str]]] = {}
        for item in self.commands_data.get("commands", []):
            name = item.get("name", "")
            cmd = item.get("command", "")
            category = self._category_from_name(name)
            grouped.setdefault(category, []).append((name, cmd))

        if not grouped:
            tab = self.left_tabs.add("General")
            ctk.CTkLabel(tab, text="No commands.").pack(padx=10, pady=10)
            self.left_tabs.set("General")
            return

        for category in sorted(grouped.keys(), key=lambda s: s.lower()):
            tab = self.left_tabs.add(category)
            scroll = ctk.CTkScrollableFrame(tab)
            scroll.pack(fill="both", expand=True, padx=10, pady=10)

            for name, cmd in grouped[category]:
                btn = ctk.CTkButton(
                    scroll,
                    text=name,
                    anchor="w",
                    command=lambda c=cmd, n=name: self.start_command_thread(c, n),
                    fg_color="#0f1b2e",
                    hover_color="#12223a",
                )
                btn.pack(fill="x", pady=4)

        first = sorted(grouped.keys(), key=lambda s: s.lower())[0]
        self.left_tabs.set(first)

    def refresh_category_options(self) -> None:
        categories = {"General"}
        for item in self.commands_data.get("commands", []):
            categories.add(self._category_from_name(item.get("name", "")))
        values = sorted(categories, key=lambda s: s.lower())
        self.category_combo.configure(values=values)
        current = (self.category_combo.get() or "").strip() or "General"
        if current not in categories:
            self.category_combo.set("General")

    def refresh_command_manager_list(self) -> None:
        # Clear old
        for child in self.cmd_list.winfo_children():
            child.destroy()
        self.cmd_row_buttons = []

        for idx, item in enumerate(self.commands_data.get("commands", [])):
            name = item.get("name", "")
            btn = ctk.CTkButton(
                self.cmd_list,
                text=f"{idx + 1}. {name}",
                anchor="w",
                fg_color="#0f1b2e",
                hover_color="#12223a",
                command=lambda i=idx: self.on_select_command(i),
            )
            btn.pack(fill="x", pady=4, padx=6)
            self.cmd_row_buttons.append(btn)

        # Keep selection if possible
        if self.selected_cmd_index is not None and 0 <= self.selected_cmd_index < len(self.cmd_row_buttons):
            self._apply_selection(self.selected_cmd_index)

    def _apply_selection(self, idx: int) -> None:
        self.selected_cmd_index = idx
        for i, btn in enumerate(self.cmd_row_buttons):
            if i == idx:
                btn.configure(fg_color="#3b82f6", hover_color="#2563eb")
            else:
                btn.configure(fg_color="#0f1b2e", hover_color="#12223a")

    # -------------------------
    # CRUD actions
    # -------------------------
    def _read_form(self) -> tuple[str, str, str]:
        category = (self.category_combo.get() or "").strip() or "General"
        name = (self.name_entry.get() or "").strip()
        cmd = (self.cmd_text.get("1.0", "end-1c") or "").strip()
        return category, name, cmd

    def on_new_command(self) -> None:
        self.selected_cmd_index = None
        self.category_combo.set("General")
        self.name_entry.delete(0, tk.END)
        self.cmd_text.delete("1.0", tk.END)
        for btn in self.cmd_row_buttons:
            btn.configure(fg_color="#0f1b2e", hover_color="#12223a")

    def on_select_command(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.commands_data.get("commands", [])):
            return
        self._apply_selection(idx)

        item = self.commands_data.get("commands", [])[idx]
        cat, nm = self._split_name(item.get("name", ""))
        self.category_combo.set(cat)
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, nm)
        self.cmd_text.delete("1.0", tk.END)
        self.cmd_text.insert("1.0", item.get("command", ""))

    def on_add_command(self) -> None:
        category, name, cmd = self._read_form()
        if not name or not cmd:
            messagebox.showerror("Error", "Name and Command cannot be empty.")
            return
        full_name = self._build_full_name(category, name)
        self.commands_data.setdefault("commands", []).append({"name": full_name, "command": cmd})
        self.refresh_left_tabs()
        self.refresh_command_manager_list()
        self.refresh_category_options()

    def on_update_command(self) -> None:
        idx = self.selected_cmd_index
        if idx is None:
            messagebox.showerror("Error", "Select an item to update.")
            return

        category, name, cmd = self._read_form()
        if not name or not cmd:
            messagebox.showerror("Error", "Name and Command cannot be empty.")
            return

        full_name = self._build_full_name(category, name)
        try:
            self.commands_data["commands"][idx] = {"name": full_name, "command": cmd}
            # Auto-save after update
            self.save_commands_to_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Updated in memory but failed to save:\n{e}")

        self.refresh_left_tabs()
        self.refresh_command_manager_list()
        self.refresh_category_options()
        self._apply_selection(idx)

    def on_delete_command(self) -> None:
        idx = self.selected_cmd_index
        if idx is None:
            messagebox.showerror("Error", "Select an item to delete.")
            return

        item = None
        try:
            item = self.commands_data.get("commands", [])[idx]
        except Exception:
            pass

        label = item.get("name") if isinstance(item, dict) else "this item"
        if not messagebox.askyesno("Confirm", f"Delete '{label}'?"):
            return

        try:
            del self.commands_data["commands"][idx]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete item: {e}")
            return

        self.selected_cmd_index = None
        self.refresh_left_tabs()
        self.refresh_command_manager_list()
        self.refresh_category_options()
        self.on_new_command()

    def on_save_commands(self) -> None:
        try:
            self.save_commands_to_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save commands.json:\n{e}")
            return
        messagebox.showinfo("Saved", f"commands.json saved to:\n{self.commands_path}")

    def on_reload_commands(self) -> None:
        self.reload_commands()

    # -------------------------
    # Manual command runner
    # -------------------------
    def on_run_manual_command(self) -> None:
        cmd = (self.manual_entry.get() or "").strip()
        if not cmd:
            return

        if cmd.lower() in {"clear", "cls"}:
            self.clear_log()
            self.manual_entry.delete(0, tk.END)
            return

        self.write_log("\n[MANUAL] Command:", "info")
        self.write_log(cmd, "info")
        self.start_command_thread(cmd, "Manual: Run Command")

    # -------------------------
    # Logging + command execution
    # -------------------------
    def write_log(self, text: str, tag: str = "info") -> None:
        self.log_queue.put((text, tag))

    def clear_log(self) -> None:
        try:
            self._log_tk.configure(state="normal")
            self._log_tk.delete("1.0", tk.END)
            self._log_tk.configure(state="disabled")
        except Exception:
            pass

    def process_queue(self) -> None:
        try:
            while True:
                msg, tag = self.log_queue.get_nowait()
                self._log_tk.configure(state="normal")
                self._log_tk.insert(tk.END, msg + "\n", tag)
                self._log_tk.see(tk.END)
                self._log_tk.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(80, self.process_queue)

    def start_command_thread(self, cmd: str, name: str) -> None:
        thread = threading.Thread(target=self.execute_command, args=(cmd, name), daemon=True)
        thread.start()

    def execute_command(self, cmd: str, name: str) -> None:
        self.write_log(f"\n[STARTING] {name}...", "info")
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert process.stdout is not None
            for line in iter(process.stdout.readline, ""):
                if line:
                    self.write_log(line.rstrip("\n"), "info")

            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                self.write_log(f"[FINISHED] {name} berhasil.", "success")
            else:
                self.write_log(f"[FAILED] {name} berhenti dengan kode {return_code}", "error")
        except Exception as e:
            self.write_log(f"[EXCEPTION] {e}", "error")

    def on_exit(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass


def main() -> None:
    root = ctk.CTk()
    ServiceManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
