# SMS draft review: approve / reject written back to Lakebase

Captured 2026-11-06 12:28 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

The operator reviews the customer SMS draft of `RCA-c7276c3238a27971` in the app. Each decision is an INSERT into the Lakebase
table `netmon_app.sms_draft_reviews` (append-only audit; who = the identity the Apps proxy forwards, when = the
database clock), done by the app's service principal. Nothing is ever sent: the table cannot hold a send
(`CHECK (sent_at IS NULL)`, `CHECK (send_channel = 'none')`) and the app has no messaging integration. Rows below are
read with psycopg as the capturing user, before and after.

## Table definition (owned by the app's Postgres role)

| conname | definition |
|---|---|
| sms_draft_reviews_decision_check | CHECK ((decision = ANY (ARRAY['approved'::text, 'rejected'::text]))) |
| sms_draft_reviews_pkey | PRIMARY KEY (review_id) |
| sms_draft_reviews_send_channel_check | CHECK ((send_channel = 'none'::text)) |
| sms_draft_reviews_sent_at_check | CHECK ((sent_at IS NULL)) |

_4 row(s)_

Owner (the app service principal's role):

| tableowner |
|---|
| 23923ae9-3de4-453b-b13f-b61f7ba84868 |

_1 row(s)_

## Before

| review_id | incident_id | summary_id | region_code | draft_sha256_12 | decision | note | reviewed_by | reviewed_at | app_identity | sent_at | send_channel |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fd9a1e73-9484-47e2-8873-4c2cc84ff6d1 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 11:34:39.669590+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| d5ad9173-d6f9-4574-8904-7e38147bb00b | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 11:34:40.732659+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| c6f091c9-935c-4586-8517-2aca204a1c56 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 12:07:00.793266+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| af760062-71a0-4b8d-a1da-dbb991aaf363 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 12:07:01.838380+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| 79a18bba-9cf1-42a6-a065-97d712d7afae | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 12:11:37.081845+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| d459d2cb-ac32-4bc5-8e1a-1f04e4099f5a | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 12:11:38.117726+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |

_6 row(s)_

The draft as the app shows it (`GET /api/incidents/{id}` -> `sms`):

```json
{
  "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
  "text": "Banksia Mobile: Sorry, no mobile service in Sydney and NSW. We'll update you as soon as we can.",
  "draft_status": "draft",
  "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
  "decision": "rejected",
  "reviewed_by": "louis.chen@databricks.com",
  "reviewed_at": "2026-11-06T12:11:38.117726+00:00",
  "sent": false,
  "note": "Draft only: this system never sends messages."
}
```

## Approve, then reject (two operator actions)

```json
{
  "request": "POST /api/incidents/{id}/sms-review {decision: approve}",
  "http_status": 200,
  "latency_ms": 1037,
  "body": {
    "review_id": "c5ccfe37-1e23-4fa9-96a3-7ce937cbe629",
    "incident_id": "RCA-c7276c3238a27971",
    "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
    "region_code": "NSW",
    "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
    "decision": "approved",
    "note": "evidence capture: approve",
    "reviewed_by": "louis.chen@databricks.com",
    "reviewed_at": "2026-11-06T12:28:56.483724+00:00",
    "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
    "sent_at": null,
    "send_channel": "none",
    "sent": false
  }
}
```

```json
{
  "request": "POST /api/incidents/{id}/sms-review {decision: reject}",
  "http_status": 200,
  "latency_ms": 1021,
  "body": {
    "review_id": "022f4cd2-bacd-4353-92ff-c116b90f71ef",
    "incident_id": "RCA-c7276c3238a27971",
    "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
    "region_code": "NSW",
    "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
    "decision": "rejected",
    "note": "evidence capture: wording",
    "reviewed_by": "louis.chen@databricks.com",
    "reviewed_at": "2026-11-06T12:28:57.500149+00:00",
    "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
    "sent_at": null,
    "send_channel": "none",
    "sent": false
  }
}
```

## Refused writes

```json
{
  "request": "POST ... {decision: approve, summary_id: <stale>}  (draft changed since the operator opened it)",
  "http_status": 409,
  "latency_ms": 1018,
  "body": {
    "error": "the draft changed since you opened it; reload and review the current draft"
  }
}
```

```json
{
  "request": "POST ... {decision: send}",
  "http_status": 400,
  "latency_ms": 1044,
  "body": {
    "error": "decision must be 'approve' or 'reject'"
  }
}
```

## After

| review_id | incident_id | summary_id | region_code | draft_sha256_12 | decision | note | reviewed_by | reviewed_at | app_identity | sent_at | send_channel |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fd9a1e73-9484-47e2-8873-4c2cc84ff6d1 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 11:34:39.669590+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| d5ad9173-d6f9-4574-8904-7e38147bb00b | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 11:34:40.732659+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| c6f091c9-935c-4586-8517-2aca204a1c56 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 12:07:00.793266+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| af760062-71a0-4b8d-a1da-dbb991aaf363 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 12:07:01.838380+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| 79a18bba-9cf1-42a6-a065-97d712d7afae | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 12:11:37.081845+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| d459d2cb-ac32-4bc5-8e1a-1f04e4099f5a | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 12:11:38.117726+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| c5ccfe37-1e23-4fa9-96a3-7ce937cbe629 | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | approved | evidence capture: approve | louis.chen@databricks.com | 2026-11-06 12:28:56.483724+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |
| 022f4cd2-bacd-4353-92ff-c116b90f71ef | RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | NSW | 69bb4b6cfb85 | rejected | evidence capture: wording | louis.chen@databricks.com | 2026-11-06 12:28:57.500149+00:00 | 23923ae9-3de4-453b-b13f-b61f7ba84868 | NULL | none |

_8 row(s)_

```json
{
  "request": "GET /api/incidents/RCA-c7276c3238a27971  -> sms",
  "http_status": 200,
  "latency_ms": 1217,
  "body": {
    "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
    "text": "Banksia Mobile: Sorry, no mobile service in Sydney and NSW. We'll update you as soon as we can.",
    "draft_status": "draft",
    "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
    "decision": "rejected",
    "reviewed_by": "louis.chen@databricks.com",
    "reviewed_at": "2026-11-06T12:28:57.500149+00:00",
    "sent": false,
    "note": "Draft only: this system never sends messages."
  }
}
```

```json
{
  "request": "GET /api/incidents/RCA-c7276c3238a27971/sms-reviews",
  "http_status": 200,
  "latency_ms": 1032,
  "body": {
    "reviews": [
      {
        "review_id": "022f4cd2-bacd-4353-92ff-c116b90f71ef",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "rejected",
        "note": "evidence capture: wording",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:28:57.500149+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "c5ccfe37-1e23-4fa9-96a3-7ce937cbe629",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "approved",
        "note": "evidence capture: approve",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:28:56.483724+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "d459d2cb-ac32-4bc5-8e1a-1f04e4099f5a",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "rejected",
        "note": "evidence capture: wording",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:11:38.117726+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "79a18bba-9cf1-42a6-a065-97d712d7afae",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "approved",
        "note": "evidence capture: approve",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:11:37.081845+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "af760062-71a0-4b8d-a1da-dbb991aaf363",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "rejected",
        "note": "evidence capture: wording",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:07:01.838380+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "c6f091c9-935c-4586-8517-2aca204a1c56",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "approved",
        "note": "evidence capture: approve",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T12:07:00.793266+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "d5ad9173-d6f9-4574-8904-7e38147bb00b",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "rejected",
        "note": "evidence capture: wording",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T11:34:40.732659+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      },
      {
        "review_id": "fd9a1e73-9484-47e2-8873-4c2cc84ff6d1",
        "incident_id": "RCA-c7276c3238a27971",
        "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
        "region_code": "NSW",
        "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
        "decision": "approved",
        "note": "evidence capture: approve",
        "reviewed_by": "louis.chen@databricks.com",
        "reviewed_at": "2026-11-06T11:34:39.669590+00:00",
        "app_identity": "23923ae9-3de4-453b-b13f-b61f7ba84868",
        "sent_at": null,
        "send_channel": "none"
      }
    ]
  }
}
```

## The table cannot record a send

Even a privileged database user trying to mark a review as sent is stopped by the constraint (run in a transaction):

```text
UPDATE netmon_app.sms_draft_reviews SET sent_at = now() WHERE incident_id = %(i)s
-> CheckViolation: new row for relation "sms_draft_reviews" violates check constraint "sms_draft_reviews_sent_at_check"
(transaction rolled back)
```
