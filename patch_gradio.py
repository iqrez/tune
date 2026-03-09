import re

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/gradio_app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Pattern for the layout
# From `with gr.Column(scale=5, elem_id="center-main"):` to `                        )` (before `with gr.Column(scale=2, elem_id="right-gauges"`)
layout_pattern = re.compile(
    r'                with gr\.Column\(scale=5, elem_id="center-main"\):\n'
    r'.*?                        \)\n'
    r'                    \)',
    re.DOTALL
)

new_layout = """                with gr.Column(scale=5, elem_id="center-main"):
                    with gr.Group(elem_id="dialog-overlay-container", elem_classes=["premium-card", "hover-panel"]):
                        # The invisible input that receives the tree selection
                        premium_tree_pick_output = gr.Textbox(visible=False, elem_id="premium-tree-pick-output")
                        
                        @gr.render(inputs=[premium_tree_pick_input])
                        def render_center_dialog(selected_node):
                            from frontend.components.dialog_renderer import render_dialog_content
                            render_dialog_content(selected_node)

                    premium_context_payload = gr.Textbox(value="", visible=False, elem_id=PREMIUM_CONTEXT_PAYLOAD_ID)
                    premium_context_trigger = gr.Button("premium-context", visible=False, elem_id=PREMIUM_CONTEXT_TRIGGER_ID)
                    premium_shortcut_payload = gr.Textbox(value="", visible=False, elem_id=PREMIUM_SHORTCUT_PAYLOAD_ID)
                    premium_shortcut_trigger = gr.Button("premium-shortcut", visible=False, elem_id=PREMIUM_SHORTCUT_TRIGGER_ID)
                    premium_context_status = gr.Textbox(label="Context/Shortcut Status", value="Ready", interactive=False)
                    gr.HTML(
                        build_context_menu_html("center-main", PREMIUM_CONTEXT_PAYLOAD_ID, PREMIUM_CONTEXT_TRIGGER_ID)
                        + build_shortcuts_js(
                            center_id="center-main",
                            burn_btn_id="btn-ribbon-burn",
                            load_btn_id="btn-ribbon-load",
                            datalog_btn_id="btn-ribbon-datalog",
                            refresh_btn_id="btn-ribbon-refresh",
                            open_table_btn_id="btn-dummy",
                            shortcut_payload_id=PREMIUM_SHORTCUT_PAYLOAD_ID,
                            shortcut_trigger_id=PREMIUM_SHORTCUT_TRIGGER_ID,
                        )
                    )"""

# Pattern for the events
events_pattern = re.compile(
    r'    # Premium suite actions\n'
    r'    demo\.load\(\n'
    r'.*?    premium_shortcut_trigger\.click\(\n'
    r'.*?        outputs=\[premium_context_status\],\n'
    r'    \)',
    re.DOTALL
)

new_events = """    # Premium suite actions
    demo.load(
        premium_refresh_registry,
        inputs=[pt_search, full_tuning_state],
        outputs=[
            full_tuning_state,
            premium_tree_html,
            premium_param_pick,
        ],
    )
    pt_search.change(
        premium_refresh_registry,
        inputs=[pt_search, full_tuning_state],
        outputs=[
            full_tuning_state,
            premium_tree_html,
            premium_param_pick,
        ],
    )
    premium_tree_pick_trigger.click(
        lambda tree_val: tree_val,
        inputs=[premium_tree_pick_input],
        outputs=[premium_param_pick],
    )
    premium_param_pick.change(
        lambda dd_val: dd_val,
        inputs=[premium_param_pick],
        outputs=[premium_tree_pick_input],
    )
    premium_context_trigger.click(
        premium_context_action,
        inputs=[premium_context_payload, full_tuning_state],
        outputs=[premium_context_status],
    )
    premium_shortcut_trigger.click(
        premium_shortcut_action,
        inputs=[premium_shortcut_payload],
        outputs=[premium_context_status],
    )"""

text = layout_pattern.sub(new_layout, text)
text = events_pattern.sub(new_events, text)

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/gradio_app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied to gradio_app.py")
