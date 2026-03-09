import re

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/gradio_app.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update Layout
layout_search = """                    with gr.Group(elem_id="dialog-overlay-container", elem_classes=["premium-card", "hover-panel"]):
                        # The invisible input that receives the tree selection
                        premium_tree_pick_output = gr.Textbox(visible=False, elem_id="premium-tree-pick-output")
                        
                        @gr.render(inputs=[premium_tree_pick_input])
                        def render_center_dialog(selected_node):
                            from frontend.components.dialog_renderer import render_dialog_content
                            render_dialog_content(selected_node)"""

layout_replace = """                    dialog_container = gr.Group(elem_id="dialog-overlay-container", elem_classes=["premium-card", "hover-panel"], visible=False)
                    with dialog_container:
                        # The invisible input that receives the tree selection
                        premium_tree_pick_output = gr.Textbox(visible=False, elem_id="premium-tree-pick-output")
                        
                        @gr.render(inputs=[premium_tree_pick_input])
                        def render_center_dialog(selected_node):
                            if not selected_node: return
                            from frontend.components.dialog_renderer import render_dialog_content
                            render_dialog_content(selected_node)
                        
                        gr.HTML("<hr style='border:1px solid #555; margin: 10px 0;'/>")
                        with gr.Row(elem_classes=["ts-dialog-footer"]):
                            btn_dialog_burn = gr.Button("Burn", elem_classes=["ts-button"])
                            btn_dialog_close = gr.Button("Close", elem_classes=["ts-button"])"""

text = text.replace(layout_search, layout_replace)

# 2. Update Events
events_search = """    premium_param_pick.change(
        lambda dd_val: dd_val,
        inputs=[premium_param_pick],
        outputs=[premium_tree_pick_input],
    )"""

events_replace = events_search + """
    premium_tree_pick_input.change(
        lambda val: gr.Group(visible=bool(val)),
        inputs=[premium_tree_pick_input],
        outputs=[dialog_container]
    )
    btn_dialog_close.click(
        lambda: (""),
        outputs=[premium_tree_pick_input]
    )
    btn_dialog_close.click(
        lambda: gr.Group(visible=False),
        outputs=[dialog_container]
    )
    btn_dialog_burn.click(
        premium_burn_all,
        inputs=[full_tuning_state],
        outputs=[full_tuning_state, premium_context_status, btn_ribbon_burn_all],
    )"""

text = text.replace(events_search, events_replace)

with open("c:/Users/Rezi/.gemini/antigravity/scratch/basetune_architect/frontend/gradio_app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch dialog footer applied!")
