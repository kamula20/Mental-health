# Presentation walkthrough

Start the server, open http://127.0.0.1:5000 and leave its terminal running. All preloaded accounts use `BetweenDemo!26`. The demonstration buttons fill those credentials. Use fictional details throughout.

## Participant journey

1. Select Start my assessment. Use `participant@between.demo` to show returning to the same account, or `BETWEEN-DEMO` for a new temporary session.
2. Complete the participation choices, background questions and social-media habits. Save and exit once to demonstrate draft recovery.
3. At Wellbeing, choose to answer the optional questionnaires. Complete every PHQ-9/GAD-7 item and the daily-life difficulty questions. Skipping these tools leaves their scores absent; it never invents a zero score.
4. Review and submit. Show the online-habits result and its answer-based explanation, followed separately by questionnaire totals and review status.
5. Start a follow-up assessment. Enter different example habits and questionnaire answers. Open My history to show both visits, their original responses and the numerical questionnaire timeline.

If an example account has already submitted, open its summary and choose Start a follow-up assessment. There is no need to delete or reset the database. Access-code sessions cannot be recovered after sign-out; use a named account when demonstrating returning later.

## Clinician journey

1. Sign in as `counsellor@between.demo` and open the participant's assigned case. Records assigned to the other clinician remain inaccessible.
2. Show the model result, completed questionnaire scores and history as separate information. If demonstrating a positive harm-related answer, use fictional responses and explain that its direct-check-in indicator is independent of model class.
3. Record a clinician conclusion. Choose Agree, Disagree or Uncertain; a disagreement requires a reason. Add a private clinical note and a separate participant message. Explicitly choose whether to share the message.
4. Schedule a future appointment, including its format and participant-visible instructions. Show it in the Follow-up dashboard. Agreed actions with past due dates appear as overdue.
5. Print the assessment report. It includes scores and clinician sign-off and omits private note text. Demonstrate that a clinician review does not replace the model's saved result.
6. Sign back in as the participant. Show only the shared message, the appointment and in-app updates. Private clinical notes and disagreement rationale stay in the staff workspace.

## Administration and invitations

1. Sign in as `admin@between.demo`.
2. Create an invitation for a fictional account, with the appropriate role.
3. Open Account mail and expand the preview. Explain that preview mode sends no email. Open the setup link in a separate browser profile/private window, set a 12+ character password and sign in.
4. Demonstrate password recovery using the same fictional email. The preview contains the single-use reset link. An expired or reused link cannot change a password.
5. Add a support-service entry only if you have actually checked its contact information and official source. For a presentation of the editing interface alone, keep an example entry hidden rather than publishing a fabricated support contact.
6. Reassign a case, review access history and show that permissions update immediately.

## Insights and evaluation

Sign in as `researcher@between.demo`. Show aggregate totals, the stored model comparison, confusion matrix and per-class errors. The current model was trained on generated data and its performance is demonstration evidence, not clinical validation. Clinical evaluation readiness describes the separate external-data workflow; no real study has been fabricated.

The external evaluation command is documented in `docs/machine-learning.md`. It requires independently labelled, consented data and keeps input records outside the public repository.

## Reliability demonstration

Run `python -m ml.check` to show that model integrity, predictions and explanations work. The portable model works without the training-library installation. A saved assessment without a result offers Calculate my result after an outage is corrected. Readiness checks, encrypted backup/restore and a production server entry point are included; actual hosting and email require operator configuration.

Validation scripts: `python -m pytest -q tests`, `python tools/browser_qa.py` and `python tools/workspace_browser_qa.py`. Browser scripts use isolated databases, not the presentation database. Their screenshots are saved under ignored `test-results/`.
