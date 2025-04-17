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
    ax_main.clear()

    # Track Y position and offset of each block for pointer drawing
    offset_to_y = {}
    offset_to_block = {}

    for block in blocks:
        height = block['size']
        if height <= 0:
            continue

        offset = block['offset']
        offset_to_y[offset] = current_y
        offset_to_block[offset] = block

        COALESCED_THRESHOLD = 4096

        if block['free'] and block['size'] >= COALESCED_THRESHOLD:
            color = '#006633'  # dark green
        elif block['free']:
            color = '#00ff88'  # light green
        else:
            color = '#ff4d4d'  # red

        rect = patches.Rectangle(
            (0.1, current_y), 0.8, height,
            linewidth=1.5, edgecolor='white', facecolor=color, alpha=0.9
        )
        ax_main.add_patch(rect)

        offset_to_y[block['offset']] = current_y + height / 2
        offset_to_block[block['offset']] = block

        label_text = f"{block['size']:,} B"
        if height > min_label_height:
            text_obj = ax_main.text(0.5, current_y + height / 2, label_text,
                                    ha='center', va='center', fontsize=11,
                                    color='white', fontweight='bold', family='monospace')
            hover_artists.append(text_obj)
            hover_labels.append((f"{block['size']:,} B", format_bytes(block['size'])))

        current_y += height

    # Draw arrows for pNext and pPrev
    #for block in blocks:
    #    start_offset = block['offset']
    #    y1 = offset_to_y_map.get(start_offset, None)
    #    if y1 is None:
    #        continue
    #
    #    for key, target_offset, is_next in [
    #        ('pNext_offset', block.get('pNext_offset'), True),
    #        ('pPrev_offset', block.get('pPrev_offset'), False)
    #    ]:
    #        if target_offset == 0 or target_offset not in offset_to_y_map:
    #            continue
    #        y2 = offset_to_y_map[target_offset]
    #
    #        arrow_color = '#00ff88' if block.get('type') == 'free' else '#ff8888'
    #        linestyle = '-' if is_next else '--'
    #
    #        ax_main.annotate(
    #            '',
    #            xy=(0.1 if is_next else 0.9, y2),
    #            xytext=(0.1 if is_next else 0.9, y1),
    #            arrowprops=dict(
    #                arrowstyle="->",
    #                color=arrow_color,
    #                linestyle=linestyle,
    #                linewidth=1.5,
    #                shrinkA=5,
    #                shrinkB=5
    #            )
    #        )

    X_POS = {
        'pPrev_free': 0.15,
        'pNext_free': 0.85,
        'pPrev_used': 0.25,
        'pNext_used': 0.75
    }

    for block in blocks:
        src_offset = block['offset']
        height = block['size']
        y_src = offset_to_y.get(src_offset, 0)
        block_type = 'free' if block.get('free') else 'used'
    
        for kind, target_key, color, linestyle in [
            ("pNext", "pNext_offset", '#00ff88' if block_type == 'free' else '#ff8888', '-'),
            ("pPrev", "pPrev_offset", '#00ff88' if block_type == 'free' else '#ff8888', '--')
        ]:
            dst_offset = block.get(target_key, 0)
            # Skip null/invalid/self-referential pointers
            if dst_offset == 0 or dst_offset == src_offset:
                continue
    
            # If the destination isn't a block, skip it
            if dst_offset not in offset_to_block:
                continue
    
            # Optional: specifically skip offset 0 even if present in map
            if dst_offset == 0 or offset_to_y.get(dst_offset, 0) < 10:
                continue
    
            y_frac = 0.3 if kind == "pNext" else 0.7
            x_frac = X_POS[f"{kind}_{block_type}"]
    
            y0 = y_src + height * y_frac
            dst_block = offset_to_block[dst_offset]
            dst_height = dst_block['size']
            y1 = offset_to_y[dst_offset] + dst_height * y_frac
    
            ax_main.annotate("",
                xy=(x_frac, y1), xytext=(x_frac, y0),
                arrowprops=dict(
                    arrowstyle="->",
                    color=color,
                    lw=1.8,
                    linestyle=linestyle,
                    alpha=0.7,
                    shrinkA=4, shrinkB=4
                )
            )

    ax_main.set_xlim(0, 1)
    ax_main.set_ylim(0, current_y + (total_height * 0.05))
    ax_main.axis('off')
    ax_main.set_title(title, fontsize=18, color='white', pad=20, fontweight='bold', family='sans-serif')

    ax_stats.clear()
    ax_stats.axis('off')
    base_y = 0.5
    line_spacing = 0.07

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
