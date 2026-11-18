# Automated learning quizzes

Automated multiple-choice quizzes are configured on a course assessment with
`assessment_type: "quiz"` and a `configuration.questions` array. Each question
has a stable `id`, prompt, two to ten options, a `correct_option_id`, and an
optional positive integer `points` weight (default 1). A quiz may contain up to
50 questions. Question and option IDs must be unique in their respective scopes.

Learners must have an active organisation membership and an approved course
enrolment. The course must be published and the assessment deadline must not
have passed.

- `GET /api/organizations/{organization_id}/learning/assessments/{assessment_id}/quiz`
  returns prompts and options only; answer keys are never returned.
- `POST /api/organizations/{organization_id}/learning/assessments/{assessment_id}/quiz-attempts`
  accepts `{ "answers": { "question_id": "option_id" } }` and requires exactly
  one valid option for every question.
- The server calculates a weighted percentage, stores the submitted answers and
  score, and reports whether the learner met the assessment pass mark.
- Configured automated quizzes cannot be submitted through the generic manual
  submission route or manually re-scored by staff. Assignments, evaluations and
  legacy quizzes without a question configuration retain the existing workflow.

The API deliberately does not return correct answers or per-question correctness
in the learner result. Detailed feedback and quiz retake policy can be added as
separate, explicitly governed programme settings.
