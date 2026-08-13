---
slug: itsmostafa-aws-agent-skills
repo: itsmostafa/aws-agent-skills
audited: 2026-05-13
commit_sha: 5df6da7060ce411e959312f07aa3cc1fad2eedd7
score: 99
exemplifies:
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: itsmostafa/aws-agent-skills

**Score**: 99/100  |  **Date**: 2026-05-13  |  **Commit**: `5df6da7060ce411e959312f07aa3cc1fad2eedd7`

A collection of 18 AWS service skills that demonstrates how to write tight, trigger-first descriptions and stay under the 500-line ceiling by offloading deep-dive content to companion files.

## Per-rule evidence

### R04 — Description as trigger

Every SKILL.md in this collection uses an identical structural pattern: a short service summary sentence followed by "Use when…" and a list of 4–7 specific action phrases that map directly to real user intents. The phrases are concrete operations, not topic summaries.

> Real quote from `skills/dynamodb/SKILL.md:3`:
>
> ```
> description: AWS DynamoDB NoSQL database for scalable data storage. Use when designing
> table schemas, writing queries, configuring indexes, managing capacity, implementing
> single-table design, or troubleshooting performance issues.
> ```

> Real quote from `skills/lambda/SKILL.md:3`:
>
> ```
> description: AWS Lambda serverless functions for event-driven compute. Use when creating
> functions, configuring triggers, debugging invocations, optimizing cold starts, setting
> up event source mappings, or managing layers.
> ```

> Real quote from `skills/iam/SKILL.md:3`:
>
> ```
> description: AWS Identity and Access Management for users, roles, policies, and
> permissions. Use when creating IAM policies, configuring cross-account access, setting
> up service roles, troubleshooting permission errors, or managing access control.
> ```

What makes these strong: each "use when" clause names a distinct operation (`configuring cross-account access`, `setting up event source mappings`) that would actually appear in a user message. Contrast with a vague alternative like "Use for IAM questions" — that phrase matches nothing specific. These descriptions also serve as distinguishing triggers: `iam` owns `cross-account access` and `permission errors`; `lambda` owns `cold starts` and `event source mappings`. No two skills overlap on trigger phrases.

### R05 — Body length

All 18 SKILL.md files stay under 500 lines. The largest (step-functions, sns) is 404 lines. Rather than cramming everything into one file and blowing past the ceiling, each service offloads its advanced material into a companion file in the same directory.

> File sizes (from `wc -l`):
>
> ```
> 404  skills/step-functions/SKILL.md   (+ workflow-patterns.md)
> 382  skills/dynamodb/SKILL.md         (+ query-patterns.md)
> 343  skills/lambda/SKILL.md           (+ deployment.md, debugging.md)
> 252  skills/iam/SKILL.md              (+ policies.md, best-practices.md)
> ```

The IAM skill demonstrates this most clearly: at 252 lines it is the shortest main file, but it has two companions (`policies.md`, `best-practices.md`) that cover the overflow content. Lambda has two companions (`deployment.md`, `debugging.md`), keeping the main file at 343 lines despite Lambda's operational surface being among the largest.

This is not accidental — every skill directory contains at least one companion file (`integration-patterns.md`, `alarms-metrics.md`, `rotation-strategies.md`, etc.), and none of the main files go over 404 lines.

### R06 — Code examples must be runnable

Every "Common Patterns" section provides complete, working code in both AWS CLI and boto3 (Python SDK) forms. The examples include actual API parameters, correct resource name placeholders, and follow-up calls needed to make the operation complete. No pseudocode.

> Real quote from `skills/dynamodb/SKILL.md:62-84` (create table, boto3 form):
>
> ```python
> import boto3
>
> dynamodb = boto3.resource('dynamodb')
>
> table = dynamodb.create_table(
>     TableName='Users',
>     KeySchema=[
>         {'AttributeName': 'PK', 'KeyType': 'HASH'},
>         {'AttributeName': 'SK', 'KeyType': 'RANGE'}
>     ],
>     AttributeDefinitions=[
>         {'AttributeName': 'PK', 'AttributeType': 'S'},
>         {'AttributeName': 'SK', 'AttributeType': 'S'}
>     ],
>     BillingMode='PAY_PER_REQUEST'
> )
>
> table.wait_until_exists()
> ```

> Real quote from `skills/s3/SKILL.md:130-154` (presigned URL):
>
> ```python
> import boto3
> from botocore.config import Config
>
> s3 = boto3.client('s3', config=Config(signature_version='s3v4'))
>
> # Generate presigned URL for download (GET)
> url = s3.generate_presigned_url(
>     'get_object',
>     Params={'Bucket': 'my-bucket', 'Key': 'path/to/file.txt'},
>     ExpiresIn=3600  # URL valid for 1 hour
> )
> ```

The `table.wait_until_exists()` call after `create_table` is the tell: a pseudocode example would stop at the API call; this one includes the follow-through that makes the snippet actually usable in a script. The presigned URL example uses `Config(signature_version='s3v4')`, which is the non-obvious requirement for URL signing — not left as an exercise for the reader.

### R08 — Patterns over theory

The skills teach via named situations rather than abstract concepts. Each "Common Patterns" section is a list of scenario headers (`Create a Table`, `Query Operations`, `Batch Operations`, `Conditional Writes`) each backed by working code. The "Troubleshooting" sections follow the same pattern: named symptom → causes → runnable debug steps.

> Real quote from `skills/dynamodb/SKILL.md:296-319` (throttling troubleshooting):
>
> ```
> ### Throttling
>
> **Symptom:** `ProvisionedThroughputExceededException`
>
> **Causes:**
> - Hot partition (uneven key distribution)
> - Burst traffic exceeding capacity
> - GSI throttling affecting base table
>
> **Solutions:**
>
> ```python
> # Use exponential backoff
> import time
> from botocore.config import Config
>
> config = Config(
>     retries={
>         'max_attempts': 10,
>         'mode': 'adaptive'
>     }
> )
> dynamodb = boto3.resource('dynamodb', config=config)
> ```
> ```

> Real quote from `skills/iam/SKILL.md:213-225` (access denied debug):
>
> ```
> **Debug steps:**
> 1. Verify identity: `aws sts get-caller-identity`
> 2. Check attached policies: `aws iam list-attached-role-policies --role-name MyRole`
> 3. Simulate the action:
>    ```bash
>    aws iam simulate-principal-policy \
>      --policy-source-arn arn:aws:iam::123456789012:role/MyRole \
>      --action-names dynamodb:GetItem \
>      --resource-arns arn:aws:dynamodb:us-east-1:123456789012:table/MyTable
>    ```
> 4. Check for explicit denies in SCPs or permission boundaries
> 5. Verify resource-based policies allow the principal
> ```

The IAM troubleshooting section is the standout: it uses `aws iam simulate-principal-policy` as a concrete debug tool rather than telling the reader to "check your permissions." The numbered steps turn what would be open-ended investigation into a deterministic procedure.

## Worth adopting

Pattern: **Companion file per overflow topic**. Evidence: `skills/lambda/deployment.md`, `skills/lambda/debugging.md`, `skills/dynamodb/query-patterns.md`, `skills/iam/policies.md`. Every skill that has content worth more than ~350 lines extracts the advanced material into a co-located companion file rather than exceeding the 500-line ceiling. The main SKILL.md stays load-time-fast; the companion is available for follow-up queries. Why it would be a useful rule: R05 tells authors to stay under 500 lines and split into "scoped sub-skills with cross-references," but gives no concrete pattern for how to name or co-locate those sub-skills. A companion-file rule (`<service>/SKILL.md` + `<service>/<topic>.md`) would make R05 actionable rather than advisory.
