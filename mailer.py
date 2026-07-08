import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_digest_email(to_address, subject, html_content):
    """뉴스레터 HTML을 이메일로 발송"""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_address

    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, to_address, msg.as_string())
        print(f"이메일 발송 완료: {to_address}")
        return True
    except Exception as e:
        print(f"⚠️ 이메일 발송 실패: {e}")
        return False
    
def render_email_html(digest_date, articles):
    """이메일 전용 HTML 생성 (인라인 스타일 사용)"""
    
    category_order = ["정치", "국제", "경제", "사회", "스포츠", "문화"]
    sorted_articles = sorted(
        articles,
        key=lambda a: category_order.index(a["category"]) if a["category"] in category_order else 999
    )

    body_parts = []
    current_category = None

    for item in sorted_articles:
        if item["category"] != current_category:
            current_category = item["category"]
            body_parts.append(f"""
                <div style="display:inline-block; background-color:#222222; color:#ffffff; 
                            font-size:16px; padding:4px 14px; margin-top:28px; margin-bottom:12px;">
                    {current_category}
                </div>
            """)

        body_parts.append(f"""
            <div style="padding:14px 0; border-bottom:1px solid #e5e0d5;">
                <a href="{item['link']}" target="_blank" 
                   style="display:block; font-size:16px; font-weight:bold; color:#1a1a1a; text-decoration:none;">
                    {item['headline']}
                </a>
                <p style="margin:6px 0 4px 0; line-height:1.6; color:#333333; font-size:14px;">
                    {item['summary']}
                </p>
                <p style="font-size:12px; color:#999999; margin:0;">
                    {item['sources']}
                </p>
            </div>
        """)

    articles_html = "".join(body_parts)

    return f"""
    <html>
    <body style="font-family: Georgia, serif; background-color:#f4f1ea; margin:0; padding:20px;">
        <table role="presentation" width="100%" style="max-width:600px; margin:0 auto; background-color:#ffffff;" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding:40px 40px 20px 40px; text-align:center; border-bottom:3px double #222222;">
                    <div style="font-size:13px; letter-spacing:2px; color:#888888; text-transform:uppercase;">
                        {digest_date}
                    </div>
                    <h1 style="font-size:28px; margin:8px 0 0 0;">아침 뉴스 브리핑</h1>
                </td>
            </tr>
            <tr>
                <td style="padding:20px 40px 40px 40px;">
                    {articles_html}
                </td>
            </tr>
        </table>
    </body>
    </html>
    """