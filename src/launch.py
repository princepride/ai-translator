import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

import gradio as gr
import jwt
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Cookie
from fastapi.responses import RedirectResponse
from gradio_fastapi import gradio_lifespan_init

from main_ui import main_ui
from utils.ui import get_base_url

# Initialize FastAPI app
app = FastAPI(lifespan=gradio_lifespan_init())

# Configuration
JWT_SECRET = "your-jwt-secret-key"  # Change this to a secure secret key
JWT_ALGORITHM = "HS256"

# Store magic links and their expiration (in a real app, use a proper database)
magic_links: Dict[str, Dict] = {}
email_whitelist = []

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "@gmail.com"  # Your email
SMTP_PASSWORD = ""  # Your app password


def create_jwt_token(email: str) -> str:
    """Create a JWT token for the user."""
    expiration = datetime.now() + timedelta(days=1)
    return jwt.encode(
        {"email": email, "exp": expiration},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


def verify_jwt_token(token: str) -> Optional[str]:
    """Verify JWT token and return email if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("email")
    except:
        return None


def send_magic_link(base_url: str, email: str) -> bool:
    """Send a magic link to the specified email address."""
    token = secrets.token_urlsafe(32)
    expiration = datetime.now() + timedelta(minutes=15)

    magic_links[token] = {
        "email": email,
        "expiration": expiration
    }

    magic_link = f"{base_url}/verify/{token}"

    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = email
    msg['Subject'] = "Your Magic Link"

    body = f"""
    Click the following link to log in:
    {magic_link}

    This link will expire in 15 minutes.
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def login_interface():
    """Create the login interface using Gradio."""
    with gr.Blocks() as login_block:
        gr.Markdown("## Login")
        email_input = gr.Textbox(label="Email", placeholder='Please enter your email address.', type='email',
                                 autofocus=True)
        submit_btn = gr.Button("Send Magic Link")
        result = gr.Markdown()

        def handle_login(email: str, request: gr.Request) -> str:
            base_url = get_base_url(request)

            if email not in email_whitelist:
                return "This email doesn't have access."

            if send_magic_link(base_url, email):
                return "Magic link sent! Please check your email."
            return "Error sending magic link. Please try again."

        submit_btn.click(
            handle_login,
            inputs=[email_input],
            outputs=[result]
        )

    return login_block


@app.get("/")
async def root(auth_token: Optional[str] = Cookie(None)):
    """Root endpoint - redirects based on auth status."""
    if auth_token and verify_jwt_token(auth_token):
        return RedirectResponse(url="/app")
    return RedirectResponse(url="/login")


@app.get("/verify/{token}")
async def verify_magic_link(token: str):
    """Verify magic link and set JWT token."""
    if token not in magic_links:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    link_data = magic_links[token]
    if datetime.now() > link_data["expiration"]:
        del magic_links[token]
        raise HTTPException(status_code=400, detail="Link expired")

    # Create JWT token
    jwt_token = create_jwt_token(link_data["email"])

    # Clean up used token
    del magic_links[token]

    # Set JWT token as cookie
    response = RedirectResponse(url="/app")
    response.set_cookie(
        key="auth_token",
        value=jwt_token,
        httponly=True,
        max_age=86400,  # 1 day
        secure=False,  # Set to True in production with HTTPS
    )
    return response


@app.get("/logout")
async def logout():
    """Log out the user by clearing the JWT cookie."""
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="auth_token")
    return response


def get_user_email(request: Request) -> Optional[str]:
    jwt_token = request.cookies.get('auth_token')
    if jwt_token is None:
        return None

    return verify_jwt_token(jwt_token)


app = gr.mount_gradio_app(app, login_interface(), path="/login")
app = gr.mount_gradio_app(app, main_ui, path="/app", auth_dependency=get_user_email)

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
