import gradio as gr


def get_base_url(request: gr.Request) -> str:
    base_url = request.headers.get('host', '')  # Gets the host (e.g., localhost:7860)
    # If you need the full URL with protocol:
    protocol = 'https' if request.headers.get('x-forwarded-proto') == 'https' else 'http'
    full_base_url = f"{protocol}://{base_url}"

    return full_base_url
