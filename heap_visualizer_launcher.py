import os
import tkinter as tk
from tkinter import messagebox
import subprocess

def get_test_prefixes():
    base_dir = "Heap_VisualLogs"
    files = os.listdir(base_dir)
    prefixes = set()
    for f in files:
        if f.startswith("Test") and f.endswith(".json"):
            prefix = f.split("_")[0] + "_"  # e.g., Test07_
            prefixes.add(prefix)
    return sorted(list(prefixes))

def launch_visualizer(prefix):
    try:
        subprocess.Popen(["python", "visualizer_multistage.py", prefix], shell=True)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch visualizer:\\n{e}")

def main():
    prefixes = get_test_prefixes()

    if not prefixes:
        print("No TestXX_ JSON logs found in Heap_VisualLogs/")
        return

    root = tk.Tk()
    root.title("Heap Visualizer Launcher")
    root.configure(bg="#1e1e1e")

    tk.Label(root, text="Select a Test to Visualize", font=("Helvetica", 14, "bold"),
             bg="#1e1e1e", fg="white").pack(pady=10)

    for prefix in prefixes:
        btn = tk.Button(root, text=prefix, width=30, font=("Consolas", 11),
                        bg="#00aa88", fg="white", activebackground="#00775f",
                        command=lambda p=prefix: launch_visualizer(p))
        btn.pack(pady=4)

    root.mainloop()

if __name__ == "__main__":
    main()