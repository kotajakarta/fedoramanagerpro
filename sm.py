import tkinter as tk
from tkinter import messagebox, scrolledtext
from tkinter import ttk
import subprocess
import json
import os
import sys
import shutil
import threading
import queue

class ServiceManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fedora Pro Manager (Stable)")
        self.root.geometry("900x650")
        self.root.minsize(700, 600)

        self.setup_style()

        self.commands_path = self.get_commands_path()
        self.commands_data = {"commands": []}
        self.command_buttons = []
        
        # Antrean untuk log agar thread-safe
        self.log_queue = queue.Queue()
        
        self.setup_ui()
        self.reload_commands()
        
        # Mulai monitor antrean log
        self.root.after(100, self.process_queue)

    def get_commands_path(self) -> str:
        """Return a writable commands.json path.

        - In PyInstaller onefile builds, bundled data lives in a temp dir (read-only-ish).
          We copy the bundled commands.json to a writable location and use that.
        - Preference order:
          1) alongside the executable (portable) if writable
          2) alongside the script (dev) if writable
          3) XDG config dir (~/.config/Service-APP-GUI)
        """

        def is_writable_dir(path: str) -> bool:
            try:
                if not os.path.isdir(path):
                    return False
                test_path = os.path.join(path, ".__write_test__")
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("ok")
                os.remove(test_path)
                return True
            except Exception:
                return False

        def resource_path(rel_path: str) -> str:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base, rel_path)

        app_dir_name = "Service-APP-GUI"

        # 1) Portable: next to executable
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            if is_writable_dir(exe_dir):
                target = os.path.join(exe_dir, "commands.json")
                self.ensure_commands_file(target, resource_path("commands.json"))
                return target

        # 2) Dev: next to script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if is_writable_dir(script_dir):
            target = os.path.join(script_dir, "commands.json")
            self.ensure_commands_file(target, resource_path("commands.json"))
            return target

        # 3) User config
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if not xdg_config_home:
            xdg_config_home = os.path.join(os.path.expanduser("~"), ".config")
        config_dir = os.path.join(xdg_config_home, app_dir_name)
        os.makedirs(config_dir, exist_ok=True)
        target = os.path.join(config_dir, "commands.json")
        self.ensure_commands_file(target, resource_path("commands.json"))
        return target

    def ensure_commands_file(self, target_path: str, template_path: str) -> None:
        """Create target commands.json if missing, copying from template when possible."""
        if os.path.exists(target_path):
            return
        try:
            if os.path.exists(template_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copyfile(template_path, target_path)
                return
        except Exception:
            pass

        # Last resort: create an empty file so CRUD still works.
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump({"commands": []}, f, ensure_ascii=False, indent=4)
                f.write("\n")
        except Exception:
            # If even this fails, load will show a readable error.
            pass

    def setup_style(self):
        # Color palette (professional + colorful)
        self.ui = {
            "bg": "#0b1220",
            "panel": "#0f1b2e",
            "panel_2": "#12223a",
            "text": "#e6eefc",
            "muted": "#9fb2d6",
            "accent": "#3b82f6",
            "accent_2": "#22c55e",
            "danger": "#ef4444",
            "border": "#223553",
        }

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        try:
            self.root.configure(bg=self.ui["bg"])
        except Exception:
            pass

        style.configure("TFrame", padding=0, background=self.ui["bg"])
        style.configure("TLabelframe", padding=10, background=self.ui["panel"], bordercolor=self.ui["border"])
        style.configure(
            "TLabelframe.Label",
            padding=(8, 2),
            background=self.ui["panel"],
            foreground=self.ui["muted"],
            font=("Sans", 9, "bold"),
        )
        style.configure("TLabel", background=self.ui["bg"], foreground=self.ui["text"])
        style.configure("Header.TLabel", font=("Sans", 14, "bold"), background=self.ui["bg"], foreground=self.ui["text"])
        style.configure("Subtle.TLabel", font=("Sans", 9), background=self.ui["bg"], foreground=self.ui["muted"])

        style.configure("TSeparator", background=self.ui["border"])

        # Notebook tabs (category)
        style.configure("TNotebook", background=self.ui["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(12, 7),
            background=self.ui["panel"],
            foreground=self.ui["muted"],
            bordercolor=self.ui["border"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.ui["accent"])],
            foreground=[("selected", "#ffffff")],
        )

        # Buttons
        style.configure(
            "TButton",
            padding=(12, 6),
            background=self.ui["panel_2"],
            foreground=self.ui["text"],
            bordercolor=self.ui["border"],
        )
        style.map(
            "TButton",
            background=[("active", self.ui["panel"])],
        )

        style.configure(
            "Accent.TButton",
            background=self.ui["accent"],
            foreground="#ffffff",
            bordercolor=self.ui["accent"],
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#2563eb"), ("pressed", "#1d4ed8")],
        )

        style.configure(
            "Success.TButton",
            background=self.ui["accent_2"],
            foreground="#052e12",
            bordercolor=self.ui["accent_2"],
        )
        style.map(
            "Success.TButton",
            background=[("active", "#16a34a"), ("pressed", "#15803d")],
            foreground=[("active", "#052e12")],
        )

        style.configure(
            "Danger.TButton",
            background=self.ui["danger"],
            foreground="#ffffff",
            bordercolor=self.ui["danger"],
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#dc2626"), ("pressed", "#b91c1c")],
        )

        style.configure(
            "Cmd.TButton",
            padding=(10, 6),
            background=self.ui["panel"],
            foreground=self.ui["text"],
            bordercolor=self.ui["border"],
            anchor="w",
        )
        style.map(
            "Cmd.TButton",
            background=[("active", self.ui["panel_2"])],
        )

    def setup_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(header, text="FEDORA SYSTEM CONTROL", style="Header.TLabel").pack(side="left")

        header_right = ttk.Frame(header)
        header_right.pack(side="right")
        ttk.Label(header_right, text="Service Manager", style="Subtle.TLabel").pack(side="left", padx=(0, 10))
        self.btn_exit = ttk.Button(header_right, text="Exit", command=self.on_exit, style="Danger.TButton")
        self.btn_exit.pack(side="left")
        ttk.Separator(self.root).pack(fill="x", padx=12, pady=(0, 10))

        # Bottom: Command Manager (CRUD commands.json)
        manager_frame = ttk.Labelframe(self.root, text="Command Manager")
        manager_frame.pack(side="bottom", fill="x", padx=12, pady=(6, 12))

        list_frame = ttk.Frame(manager_frame)
        list_frame.pack(side="left", fill="both", expand=True, padx=(6, 10), pady=6)

        self.cmd_listbox = tk.Listbox(
            list_frame,
            height=6,
            activestyle="none",
            selectmode="browse",
            exportselection=False,
            bg=self.ui["panel_2"],
            fg=self.ui["text"],
            selectbackground=self.ui["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=self.ui["border"],
        )
        self.cmd_listbox.pack(side="left", fill="both", expand=True)

        list_scroll = tk.Scrollbar(list_frame, orient="vertical", command=self.cmd_listbox.yview)
        list_scroll.pack(side="right", fill="y")
        self.cmd_listbox.configure(yscrollcommand=list_scroll.set)

        form_frame = ttk.Frame(manager_frame)
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=6)

        ttk.Label(form_frame, text="Category").grid(row=0, column=0, sticky="w")
        self.cmd_category_var = tk.StringVar(value="General")
        self.cmd_category_combo = ttk.Combobox(
            form_frame,
            textvariable=self.cmd_category_var,
            values=["General"],
            state="readonly",
            width=20,
        )
        self.cmd_category_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(form_frame, text="Name").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.cmd_name_var = tk.StringVar()
        self.cmd_name_entry = ttk.Entry(form_frame, textvariable=self.cmd_name_var, width=45)
        self.cmd_name_entry.grid(row=1, column=1, sticky="we", padx=(8, 0), pady=(6, 0))

        ttk.Label(form_frame, text="Command").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        self.cmd_text = tk.Text(form_frame, height=3, width=45)
        self.cmd_text.grid(row=2, column=1, sticky="we", padx=(8, 0), pady=(6, 0))

        try:
            self.cmd_text.configure(
                bg=self.ui["panel_2"],
                fg=self.ui["text"],
                insertbackground=self.ui["text"],
                highlightthickness=1,
                highlightbackground=self.ui["border"],
                relief="flat",
            )
        except Exception:
            pass

        actions_frame = ttk.Frame(form_frame)
        actions_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.btn_new = ttk.Button(actions_frame, text="New", width=10, command=self.on_new_command)
        self.btn_new.pack(side="left", padx=(0, 6))
        self.btn_add = ttk.Button(actions_frame, text="Add", width=10, command=self.on_add_command, style="Accent.TButton")
        self.btn_add.pack(side="left", padx=(0, 6))
        self.btn_update = ttk.Button(actions_frame, text="Update", width=10, command=self.on_update_command, style="Success.TButton")
        self.btn_update.pack(side="left", padx=(0, 6))
        self.btn_delete = ttk.Button(actions_frame, text="Delete", width=10, command=self.on_delete_command, style="Danger.TButton")
        self.btn_delete.pack(side="left", padx=(0, 6))
        self.btn_save = ttk.Button(actions_frame, text="Save", width=10, command=self.on_save_commands, style="Accent.TButton")
        self.btn_save.pack(side="left", padx=(0, 6))
        self.btn_reload = ttk.Button(actions_frame, text="Reload", width=10, command=self.on_reload_commands)
        self.btn_reload.pack(side="left")

        form_frame.columnconfigure(1, weight=1)

        self.cmd_listbox.bind("<<ListboxSelect>>", self.on_select_command)

        # Main Container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(side="top", fill="both", expand=True, padx=12, pady=8)

        # Left: Button Area
        self.btn_notebook = ttk.Notebook(main_frame)
        self.btn_notebook.pack(side="left", fill="y", padx=(0, 10))

        # Right: Manual command + Log Area
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        manual_frame = ttk.Labelframe(right_frame, text="Manual Command")
        manual_frame.pack(fill="x", pady=(0, 8))

        self.manual_cmd_var = tk.StringVar()
        self.manual_cmd_entry = ttk.Entry(manual_frame, textvariable=self.manual_cmd_var)
        self.manual_cmd_entry.pack(side="left", fill="x", expand=True, padx=(6, 6), pady=6)

        self.manual_run_btn = ttk.Button(manual_frame, text="Run", command=self.on_run_manual_command, style="Accent.TButton")
        self.manual_run_btn.pack(side="left", padx=(0, 6), pady=6)

        self.manual_cmd_entry.bind("<Return>", lambda e: self.on_run_manual_command())

        self.log_area = scrolledtext.ScrolledText(
            right_frame,
            bg="#08101e",
            fg=self.ui["text"],
            font=("Monospace", 9),
            insertbackground=self.ui["text"],
        )
        self.log_area.pack(fill="both", expand=True)
        self.log_area.tag_config("info", foreground=self.ui["muted"])
        self.log_area.tag_config("success", foreground=self.ui["accent_2"])
        self.log_area.tag_config("error", foreground=self.ui["danger"])

    def _category_from_name(self, name: str) -> str:
        if not isinstance(name, str):
            return "General"
        if ":" in name:
            prefix = name.split(":", 1)[0].strip()
            return prefix or "General"
        return "General"

    def _make_scrollable_frame(self, parent):
        container = tk.Frame(parent)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.ui.get("border", "#223553"),
            bg=self.ui.get("panel", "#0f1b2e"),
        )
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas)
        try:
            inner.configure(bg=self.ui.get("panel", "#0f1b2e"))
        except Exception:
            pass
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                delta = getattr(event, "delta", 0)
                if delta:
                    canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        return container, inner

    def load_commands_from_disk(self):
        if not os.path.exists(self.commands_path):
            raise FileNotFoundError(f"commands.json not found at {self.commands_path}")
        with open(self.commands_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "commands" not in data or not isinstance(data.get("commands"), list):
            raise ValueError("Invalid commands.json format. Expected { 'commands': [ ... ] }")
        normalized = []
        for item in data.get("commands", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            cmd = str(item.get("command", "")).strip()
            if not name or not cmd:
                continue
            normalized.append({"name": name, "command": cmd})
        self.commands_data = {"commands": normalized}

    def save_commands_to_disk(self):
        with open(self.commands_path, "w", encoding="utf-8") as f:
            json.dump(self.commands_data, f, ensure_ascii=False, indent=4)
            f.write("\n")

    def clear_command_buttons(self):
        if hasattr(self, "btn_notebook"):
            for tab_id in list(self.btn_notebook.tabs()):
                try:
                    tab_widget = self.btn_notebook.nametowidget(tab_id)
                    self.btn_notebook.forget(tab_id)
                    tab_widget.destroy()
                except Exception:
                    pass
        for btn in self.command_buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        self.command_buttons = []

    def refresh_command_buttons(self):
        self.clear_command_buttons()
        if not hasattr(self, "btn_notebook"):
            return

        grouped = {}
        for item in self.commands_data.get("commands", []):
            name = item.get("name", "")
            cmd = item.get("command", "")
            category = self._category_from_name(name)
            grouped.setdefault(category, []).append((name, cmd))

        for category in sorted(grouped.keys(), key=lambda s: s.lower()):
            tab = tk.Frame(self.btn_notebook)
            try:
                tab.configure(bg=self.ui["bg"])
            except Exception:
                pass
            self.btn_notebook.add(tab, text=category)
            _, inner = self._make_scrollable_frame(tab)

            for name, cmd in grouped[category]:
                btn = ttk.Button(
                    inner,
                    text=name,
                    width=30,
                    command=lambda c=cmd, n=name: self.start_command_thread(c, n),
                    style="Cmd.TButton",
                )
                btn.pack(fill="x", pady=3)
                self.command_buttons.append(btn)

    def reload_commands(self):
        try:
            self.load_commands_from_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load commands.json:\n{e}")
            self.commands_data = {"commands": []}
        self.refresh_command_buttons()
        self.refresh_command_list()
        self.refresh_category_options()

    def refresh_category_options(self):
        if not hasattr(self, "cmd_category_combo"):
            return
        categories = {"General"}
        for item in self.commands_data.get("commands", []):
            categories.add(self._category_from_name(item.get("name", "")))
        values = sorted(categories, key=lambda s: s.lower())
        self.cmd_category_combo.configure(values=values)
        current = (self.cmd_category_var.get() or "").strip() or "General"
        if current not in categories:
            self.cmd_category_var.set("General")

    def refresh_command_list(self):
        if not hasattr(self, "cmd_listbox"):
            return
        self.cmd_listbox.delete(0, tk.END)
        for idx, item in enumerate(self.commands_data.get("commands", [])):
            name = item.get("name", "")
            self.cmd_listbox.insert(tk.END, f"{idx + 1}. {name}")

    def get_selected_index(self):
        if not hasattr(self, "cmd_listbox"):
            return None
        sel = self.cmd_listbox.curselection()
        if not sel:
            return None
        return int(sel[0])

    def on_select_command(self, event=None):
        idx = self.get_selected_index()
        if idx is None:
            return
        try:
            item = self.commands_data.get("commands", [])[idx]
        except Exception:
            return
        full_name = item.get("name", "")
        if isinstance(full_name, str) and ":" in full_name:
            cat, rest = full_name.split(":", 1)
            cat = (cat or "").strip() or "General"
            rest = (rest or "").strip()
            self.cmd_category_var.set(cat)
            self.cmd_name_var.set(rest)
        else:
            self.cmd_category_var.set("General")
            self.cmd_name_var.set(full_name if isinstance(full_name, str) else "")
        self.cmd_text.delete("1.0", tk.END)
        self.cmd_text.insert(tk.END, item.get("command", ""))

    def on_new_command(self):
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_category_var.set("General")
        self.cmd_name_var.set("")
        self.cmd_text.delete("1.0", tk.END)
        self.cmd_name_entry.focus_set()

    def _read_form(self):
        category = (self.cmd_category_var.get() or "").strip() or "General"
        name = (self.cmd_name_var.get() or "").strip()
        cmd = (self.cmd_text.get("1.0", tk.END) or "").strip()
        return category, name, cmd

    def _build_full_name(self, category: str, name: str) -> str:
        category = (category or "").strip() or "General"
        name = (name or "").strip()
        if category.lower() == "general" or not category:
            return name
        return f"{category}: {name}"

    def on_add_command(self):
        category, name, cmd = self._read_form()
        if not name or not cmd:
            messagebox.showerror("Error", "Name and Command cannot be empty.")
            return
        full_name = self._build_full_name(category, name)
        self.commands_data.setdefault("commands", []).append({"name": full_name, "command": cmd})
        self.refresh_command_buttons()
        self.refresh_command_list()
        self.refresh_category_options()
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(tk.END)
        self.cmd_listbox.activate(tk.END)

    def on_update_command(self):
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showerror("Error", "Select an item to update.")
            return
        category, name, cmd = self._read_form()
        if not name or not cmd:
            messagebox.showerror("Error", "Name and Command cannot be empty.")
            return
        try:
            full_name = self._build_full_name(category, name)
            self.commands_data["commands"][idx] = {"name": full_name, "command": cmd}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update item: {e}")
            return

        # Auto-save after update
        try:
            self.save_commands_to_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Updated in memory but failed to save commands.json:\n{e}")

        self.refresh_command_buttons()
        self.refresh_command_list()
        self.refresh_category_options()
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(idx)
        self.cmd_listbox.activate(idx)

    def on_delete_command(self):
        idx = self.get_selected_index()
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
        self.refresh_command_buttons()
        self.refresh_command_list()
        self.refresh_category_options()
        self.on_new_command()

    def on_save_commands(self):
        try:
            self.save_commands_to_disk()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save commands.json:\n{e}")
            return
        messagebox.showinfo("Saved", f"commands.json saved to:\n{self.commands_path}")

    def on_reload_commands(self):
        self.reload_commands()

    def write_log(self, text, tag="info"):
        self.log_queue.put((text, tag))

    def on_exit(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def on_run_manual_command(self):
        cmd = (self.manual_cmd_var.get() or "").strip()
        if not cmd:
            return

        if cmd.lower() in {"clear", "cls"}:
            try:
                self.log_area.configure(state='normal')
                self.log_area.delete("1.0", tk.END)
                self.log_area.configure(state='disabled')
            except Exception:
                pass
            self.manual_cmd_var.set("")
            return

        self.write_log("\n[MANUAL] Command:", "info")
        self.write_log(cmd, "info")
        self.start_command_thread(cmd, "Manual: Run Command")

    def process_queue(self):
        """Update GUI dari antrean (dijalankan di main thread)"""
        try:
            while True:
                msg, tag = self.log_queue.get_nowait()
                self.log_area.configure(state='normal')
                self.log_area.insert(tk.END, msg + "\n", tag)
                self.log_area.see(tk.END)
                self.log_area.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def start_command_thread(self, cmd, name):
        """Menjalankan perintah di thread terpisah agar tidak freeze"""
        thread = threading.Thread(target=self.execute_command, args=(cmd, name))
        thread.daemon = True
        thread.start()

    def execute_command(self, cmd, name):
        self.write_log(f"\n[STARTING] {name}...", "info")
        try:
            # Menggunakan shell=True dan stdbuf agar output streaming lancar
            process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )

            # Membaca output baris demi baris secara real-time
            for line in iter(process.stdout.readline, ""):
                if line:
                    self.write_log(line.strip())
            
            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                self.write_log(f"[FINISHED] {name} berhasil.", "success")
            else:
                self.write_log(f"[FAILED] {name} berhenti dengan kode {return_code}", "error")
                
        except Exception as e:
            self.write_log(f"[EXCEPTION] {str(e)}", "error")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServiceManagerApp(root)
    root.mainloop()