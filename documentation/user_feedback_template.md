# User Feedback Survey Template

Below is the structured questionnaire used to validate system usability and trust with parent focus groups:

## Survey Questions

### 1. Is the ETA easy to understand?
- **Scale**: 1 (Strongly Disagree) to 5 (Strongly Agree)
- **Objective**: Assess presentation clarity of dynamic arrival predictions.

### 2. Is the delay explanation useful?
- **Scale**: 1 (Strongly Disagree) to 5 (Strongly Agree)
- **Objective**: Measure if the delay reason breakdown (traffic, boarding, sensors) adds value.

### 3. Does the system make you trust the ETA more?
- **Scale**: 1 (Strongly Disagree) to 5 (Strongly Agree)
- **Objective**: Evaluate trust enhancement when explanations are present.

### 4. Would this system reduce the need to contact the school for bus status?
- **Scale**: 1 (Strongly Disagree) to 5 (Strongly Agree)
- **Objective**: Validate the simulated 60% call reduction metric.

### 5. Is the in-app notification clear?
- **Scale**: 1 (Strongly Disagree) to 5 (Strongly Agree)
- **Objective**: Check if warning color codes (Green/Yellow/Red) are readable and clear.

---

## Sample Data Collection Format

Survey results are recorded in SQLite using the `feedback` table. Each entry stores:
- `id` (INTEGER, Primary Key)
- `timestamp` (TEXT)
- `q1` to `q5` (INTEGER values from 1 to 5)
- `comments` (TEXT comments)
