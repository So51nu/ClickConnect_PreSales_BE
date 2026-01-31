# core/views_static.py
from django.http import HttpResponse


def privacy_policy(request):
    html = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>Privacy Policy - MyCiti PreSale</title>
      </head>
      <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 900px; margin: auto; line-height: 1.6;">
        <h1>Privacy Policy</h1>
        <p><b>Last updated:</b> 22 Dec 2025</p>

        <p>
          This Privacy Policy describes how we collect, use, and protect personal information
          submitted via Meta/Facebook Lead Ads.
        </p>

        <h3>Information We Collect</h3>
        <ul>
          <li>Name</li>
          <li>Phone number</li>
          <li>Email address</li>
          <li>Any other fields you submit in the Lead Form</li>
        </ul>

        <h3>How We Use Information</h3>
        <p>
          Information is used only to contact users regarding real estate services and inquiries,
          and to manage leads inside our CRM system.
        </p>

        <h3>Data Sharing</h3>
        <p>
          We do not sell personal data. Data is accessible only to authorized staff and required
          service providers for hosting/CRM operations.
        </p>

        <h3>Data Retention</h3>
        <p>
          We retain lead data only as long as required for business and legal purposes,
          then delete or anonymize it.
        </p>

        <h3>Contact</h3>
        <p>Email: <a href="mailto:sonuyadav2192004@gmail.com">sonuyadav2192004@gmail.com</a></p>
      </body>
    </html>
    """
    return HttpResponse(html)


def data_deletion(request):
    html = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>User Data Deletion - MyCiti PreSale</title>
      </head>
      <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 900px; margin: auto; line-height: 1.6;">
        <h1>User Data Deletion</h1>
        <p>
          If you want your personal data deleted, please email us at:
        </p>
        <p>
          <b><a href="mailto:sonuyadav2192004@gmail.com">sonuyadav2192004@gmail.com</a></b><br/>
          Subject: <b>Delete My Data</b>
        </p>
        <p>
          Please include the phone number or email you submitted in the lead form so we can identify your data.
        </p>
      </body>
    </html>
    """
    return HttpResponse(html)
