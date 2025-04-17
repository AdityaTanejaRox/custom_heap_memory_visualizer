import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from matplotlib.widgets import Button
import os
import sys
import re

def logical_sort_key(fname):
    name = fname.replace(".json", "")
    if "Init" in name:
        return 0
    elif "Malloc" in name:
        return 1
    elif "Free" in name:
        return 2
    else:
        # fallback: if we find a number (e.g. 16 in Test16_) use that
        match = re.search(r'(\d+)', name)
        return int(match.group(1)) if match else 99

# Convert byte counts to human-readable format (e.g., KB, MB)
def format_bytes(value):
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} MB"
    elif value >= 1024:
        return f"{value / 1024:.2f} KB"
    else:
        return f"{value:,} B"

def load_snapshot(path):
    with open(path, 'r') as f:
        return json.load(f)

# Draw a single snapshot (heap state) with blocks and statistics
def draw_snapshot(snapshot, title, ax_main, ax_stats, hover_artists, hover_labels):
    blocks = snapshot['blocks']
    stats = snapshot.get('stats', {})

    total_height = sum(block['size'] for block in blocks if block['size'] > 0)
    current_y = 0
    min_label_height = total_height * 0.03

    hover_artists.clear()
    hover_labels.clear()

    # Iterate over each memory block
    for block in blocks:
        height = block['size']
        # Ignore zero-size or invalid blocks
        if height <= 0:
            continue

       # Consider a block coalesced if it's free and bigger than a meaningful static size
        COALESCED_THRESHOLD = 4096  # 4 KB, adjust as needed

        if block['free'] and block['size'] >= COALESCED_THRESHOLD:
           color = '#006633'  # dark green
        elif block['free']:
           color = '#00ff88'  # light green
        else:
            color = '#ff4d4d'  # red (used)

        # Draw the memory block as a rectangle
        rect = patches.Rectangle(
            (0.1, current_y), 0.8, height,
            linewidth=1.5, edgecolor='white', facecolor=color, alpha=0.9
        )
        ax_main.add_patch(rect)

        label_text = f"{block['size']:,} B"
        # Only label if the block is tall enough
        if height > min_label_height:
            text_obj = ax_main.text(0.5, current_y + height / 2, label_text,
                                    ha='center', va='center', fontsize=11,
                                    color='white', fontweight='bold', family='monospace')
            hover_artists.append(text_obj)
            hover_labels.append((f"{block['size']:,} B", format_bytes(block['size'])))

        current_y += height

    ax_main.set_xlim(0, 1)
    ax_main.set_ylim(0, current_y + (total_height * 0.05))
    ax_main.axis('off')
    ax_main.set_title(title, fontsize=18, color='white', pad=20, fontweight='bold', family='sans-serif')

    ax_stats.clear()
    ax_stats.axis('off')
    base_y = 0.5
    line_spacing = 0.07

    # Heap statistics labels on right side
    ax_stats.text(0, base_y + 2*line_spacing, "*** Heap Stats ***", fontsize=15, va='center',
                  family='sans-serif', color='white', fontweight='bold')
    ax_stats.text(0, base_y + line_spacing, f"Used Mem : {format_bytes(stats.get('total_used_mem', 0))}",
                  fontsize=11, family='monospace', color='white', va='center')
    ax_stats.text(0, base_y, f"Free Mem : {format_bytes(stats.get('total_free_mem', 0))}",
                  fontsize=11, family='monospace', color='white', va='center')
    ax_stats.text(0, base_y - line_spacing, f"Used Blks: {stats.get('num_used_blocks', 0)}",
                  fontsize=11, family='monospace', color='white', va='center')
    ax_stats.text(0, base_y - 2*line_spacing, f"Free Blks: {stats.get('num_free_blocks', 0)}",
                  fontsize=11, family='monospace', color='white', va='center')

# Animate through the sequence of heap snapshots
def animate_sequence(snapshots, titles):
    plt.style.use('dark_background')
    fig, (ax_main, ax_stats) = plt.subplots(1, 2, figsize=(10, 10), width_ratios=[4, 1])
    fig.patch.set_facecolor('#1e1e1e')
    fig.subplots_adjust(top=0.9)

    hover_artists = []
    hover_labels = []

    state = {'paused': False}

    # Update the current animation frame
    def update(frame):
        if not state['paused']:
            ax_main.clear()
            draw_snapshot(snapshots[frame], titles[frame], ax_main, ax_stats, hover_artists, hover_labels)

    # Toggle label format on mouse hover
    def on_motion(event):
        for text, (raw, human) in zip(hover_artists, hover_labels):
            contains, _ = text.contains(event)
            if contains:
                current = text.get_text()
                text.set_text(human if current == raw else raw)
                fig.canvas.draw_idle()

    def toggle_pause(event):
        state['paused'] = not state['paused']

    ani = animation.FuncAnimation(
        fig, update, frames=len(snapshots), interval=1500, repeat=True
    )
    fig.canvas.mpl_connect("motion_notify_event", on_motion)

    btn_ax = plt.axes([0.80, 0.05, 0.13, 0.05])
    btn = Button(btn_ax, 'Pause/Play', color='#444', hovercolor='#666')
    btn.label.set_fontsize(10)
    btn.label.set_color('white')
    btn.on_clicked(toggle_pause)
    plt.show()

# Entry point: loads JSON logs and starts the animation UI
def main():
    if len(sys.argv) != 2:
        print("Usage: python visualizer_multistage.py TestXX_")
        return

    prefix = sys.argv[1]
    base_dir = "Heap_VisualLogs"

    all_files = os.listdir(base_dir)
    json_files = [
        f for f in all_files
        if f.startswith(prefix) and f.endswith(".json")
    ]

    if not json_files:
        print(f"No matching JSON files for prefix '{prefix}' in {base_dir}/")
        return

    snapshots_with_titles = []

    for fname in json_files:
        path = os.path.join(base_dir, fname)
        try:
            data = load_snapshot(path)
            step = data.get("step", 9999)  # fallback to end if missing
            snapshots_with_titles.append((step, data, fname.replace(".json", "")))
        except Exception as e:
            print(f"Failed to load {fname}: {e}")

    # Sort all snapshots based on embedded "step" value
    snapshots_with_titles.sort(key=lambda tup: tup[0])

    # Unpack into two clean lists
    snapshots = [item[1] for item in snapshots_with_titles]
    titles = [item[2] for item in snapshots_with_titles]

    if snapshots:
        animate_sequence(snapshots, titles)
    else:
        print("No valid snapshots loaded.")

if __name__ == "__main__":
    main()
