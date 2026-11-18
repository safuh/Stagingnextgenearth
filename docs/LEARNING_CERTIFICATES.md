# Learning certificates

A certificate is issued when the learner completes every course lesson and passes
every configured assessment. The learner classroom exposes a PDF download once
the credential has been issued.

`GET /api/organizations/{organization_id}/learning/certificates/{certificate_id}/download`
returns a one-page landscape A4 PDF. Access is limited to the enrolled learner
and authorised learning managers in the same organisation. Revoked credentials
return HTTP 410 and cannot be downloaded. Responses are marked `private, no-store`.

The PDF includes the certificate number, course, organisation, issue date, a
verification code, and a QR code linking to the public verification page.
`PUBLIC_BASE_URL` controls the QR destination and defaults to
`https://nextgenforearth.org`; production configuration must use HTTPS. The QR
page automatically verifies its `code` query parameter. Public verification
reveals credential validity and course details, not learner account information.

Where a learner has a researcher profile, the PDF uses that profile's display
name. Otherwise it uses the account identifier as the recipient label; learners
should maintain an appropriate display name before issuing a credential they
intend to share publicly.
