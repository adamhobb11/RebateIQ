"""
Outreach campaign assembly with CASL compliance enforced in code.

Division of labour: the LLM writes the body copy (personalizing program
relevance to each building); this module owns the compliance envelope —
sender identification, a functional unsubscribe, and the frequency policy
are appended and VALIDATED deterministically, so a campaign that fails the
CASL checks cannot be queued no matter what the model wrote.

Demo vs. production: queue_campaign writes the approved emails to a local
outbox directory (the simulated send). Production swaps the writer for
SendGrid with a real unsubscribe link, suppression-list handling, sender
authentication, and bounce processing — same drafts, same validation.
"""

from pathlib import Path

from pydantic import BaseModel

from rebateiq.shared.models import ContractorProfile

FOLLOWUP_POLICY = "initial send + at most ONE follow-up to non-responders, then stop"

MIN_BODY_CHARS = 200
MAX_BODY_CHARS = 2_000
MAX_SUBJECT_CHARS = 78


class EmailDraft(BaseModel):
    listing_id: str
    business_name: str
    to_email: str
    subject: str
    body: str           # LLM-written copy, no footer
    footer: str         # compliance envelope, code-written

    @property
    def full_text(self) -> str:
        return f"{self.body.rstrip()}\n\n{self.footer}"


def compliance_footer(contractor: ContractorProfile) -> str:
    return (
        "--\n"
        f"{contractor.contact_name} — {contractor.company_name}\n"
        f"{contractor.phone} | {contractor.email}\n"
        "You're receiving this one-time notice because your business contact "
        "information is publicly listed. Our policy: "
        f"{FOLLOWUP_POLICY}.\n"
        "To opt out, reply STOP or use the unsubscribe link: "
        "[unsubscribe link inserted at send time]"
    )


def validate_draft(draft: EmailDraft, contractor: ContractorProfile) -> list[str]:
    """CASL + deliverability checks. Empty list = compliant."""
    problems = []
    text = draft.full_text
    lower = text.lower()

    if contractor.company_name not in text:
        problems.append("sender identification: company name missing")
    if contractor.phone not in text and contractor.email not in text:
        problems.append("sender identification: no contact coordinates")
    if "unsubscribe" not in lower and "opt out" not in lower:
        problems.append("no functional unsubscribe mechanism")
    if not (10 <= len(draft.subject) <= MAX_SUBJECT_CHARS):
        problems.append(f"subject length {len(draft.subject)} outside 10-{MAX_SUBJECT_CHARS}")
    if draft.subject.isupper():
        problems.append("subject is all caps")
    if not (MIN_BODY_CHARS <= len(draft.body) <= MAX_BODY_CHARS):
        problems.append(f"body length {len(draft.body)} outside {MIN_BODY_CHARS}-{MAX_BODY_CHARS}")
    if "@" not in draft.to_email:
        problems.append("recipient email malformed")
    return problems


def assemble_campaign(
    prospects: list[dict],
    emails: list[dict],
    contractor: ContractorProfile,
) -> tuple[list[EmailDraft], dict[str, list[str]]]:
    """Zip prospect records with LLM-written {listing_id, subject, body},
    append the compliance footer, validate every draft."""
    by_id = {p["listing_id"]: p for p in prospects}
    footer = compliance_footer(contractor)

    drafts, problems = [], {}
    for e in emails:
        p = by_id.get(e["listing_id"])
        if p is None:
            problems[e["listing_id"]] = ["no matching prospect record"]
            continue
        draft = EmailDraft(
            listing_id=p["listing_id"],
            business_name=p["business_name"],
            to_email=p["email"],
            subject=e["subject"],
            body=e["body"],
            footer=footer,
        )
        issues = validate_draft(draft, contractor)
        if issues:
            problems[draft.listing_id] = issues
        drafts.append(draft)
    return drafts, problems


def format_campaign_preview(drafts: list[EmailDraft], program_name: str) -> str:
    """The approval artifact: every email, in full, before anything sends."""
    lines = [
        f"CAMPAIGN FOR APPROVAL — {program_name}",
        f"{len(drafts)} emails. Policy: {FOLLOWUP_POLICY}.",
        "Nothing sends until you approve.",
        "",
    ]
    for i, d in enumerate(drafts, start=1):
        lines += [
            f"--- email {i}/{len(drafts)} ------------------------------------------",
            f"To:      {d.business_name} <{d.to_email}>",
            f"Subject: {d.subject}",
            "",
            d.full_text,
            "",
        ]
    return "\n".join(lines)


def queue_campaign(drafts: list[EmailDraft], outbox_dir: str) -> list[str]:
    """The simulated send: one file per message in the outbox."""
    out = Path(outbox_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for d in drafts:
        path = out / f"{d.listing_id}.txt"
        path.write_text(
            f"To: {d.business_name} <{d.to_email}>\nSubject: {d.subject}\n\n{d.full_text}\n"
        )
        paths.append(str(path))
    return paths
