**Contributing to KelDev**

Thank you for your interest in contributing to KelDev!

KelDev is a collaborative platform where people work together on projects, solve tasks, and help improve the platform itself. Every contribution, from fixing a bug to implementing a new feature, is welcome.

This guide explains how to set up your development environment, run KelDev locally, and submit your changes for review.

1. Requirements

Before you begin, make sure you have:

- Python compatible with the project's dependencies.
- Git.
- A GitHub account.
- A code editor.
- An internet connection.

You do not need to be an expert developer. Small, focused contributions are welcome.

2. Fork the Repository

1. Open the "KelDev repository" (https://github.com/elspanish/KelDev).
2. Click Fork in the upper-right corner.
3. Create a fork under your own GitHub account.
4. Open your fork and copy its HTTPS URL.

Your fork is your own copy of the repository. You can make changes there without affecting the live application.

3. Clone Your Fork

Open a terminal and run:

git clone https://github.com/YOUR-USERNAME/KelDev.git
cd KelDev

Replace "YOUR-USERNAME" with your GitHub username.

Create a separate branch for your contribution:

git switch -c feature/your-change

For example:

git switch -c fix/login-error

Use a descriptive name that reflects your contribution.

4. Install Dependencies

Create and activate a virtual environment.

Windows:

py -m venv .venv
.venv\Scripts\activate

macOS / Linux:

python3 -m venv .venv
source .venv/bin/activate

Install the project's dependencies:

python -m pip install --upgrade pip
pip install -r requirements.txt

If a dependency is added or changed, update "requirements.txt" accordingly.

5. Configure Environment Variables

KelDev uses environment variables to configure external services, including Supabase and AI providers.

The example configuration is located at:

"pcapp/.env.example"

Create your local environment file by copying the example.

macOS / Linux:

cp pcapp/.env.example pcapp/.env

Windows PowerShell:

Copy-Item pcapp/.env.example pcapp/.env

Open "pcapp/.env" and replace the placeholder values with your own development credentials.

The example file contains these variables:

Variable| Purpose
"SUPABASE_URL"| URL of your Supabase project.
"SUPABASE_KEY"| Supabase key used by the application.
"GROQ_API_KEY"| API key for Groq.
"GROQ_MODEL"| Groq model used by the application.
"GEMINI_API_KEY"| API key for Google Gemini.
"GEMINI_MODEL"| Primary Gemini model.
"GEMINI_FALLBACK_MODEL"| Fallback Gemini model.

Keep the model names provided in ".env.example" unless you know that a change is necessary.

Supabase

Some features require a Supabase project.

If your task needs database access, configure your development environment using the appropriate Supabase project URL and key. Consult the project's database setup documentation and "schema.sql" if database initialization is required.

Do not use production credentials or make destructive changes to a production database.

AI Providers

Some features may require access to Groq or Gemini.

Obtain the appropriate credentials from the providers' official websites and configure them locally.

Not every contribution will require both providers. Check the code involved in your task before obtaining additional credentials.

Security

Never commit your ".env" file or publish API keys, passwords, tokens, or database credentials.

Only commit ".env.example" when updating the example configuration, and never put real credentials in it.

Do not change the application's production secrets or configuration as part of an ordinary contribution.

6. Run KelDev Locally

From the repository root, run:

streamlit run pcapp/main.py

Streamlit should display a local URL in your terminal. Open it in your browser to access the application.

If the application fails to start, check that:

- Your virtual environment is activated.
- Dependencies have been installed.
- Required environment variables are configured.
- Your local configuration uses valid credentials for the services required by the application.

If you encounter an issue that prevents you from testing your contribution, explain it in your pull request.

7. Make Your Changes

Before writing code, make sure you understand the task and what the expected result should be.

Good contributions include:

- Fixing bugs.
- Improving existing features.
- Improving the user interface.
- Adding tests.
- Improving performance and reliability.
- Updating documentation.
- Implementing approved features.

Please follow these guidelines:

- Keep changes focused on the task.
- Follow the existing code style and project structure.
- Avoid modifying unrelated files.
- Avoid introducing unnecessary dependencies.
- Do not commit secrets, virtual environments, or generated files.
- Test your changes before submitting them.

For substantial changes, discuss the proposed approach with the maintainer before investing significant time in implementation.

8. Test Your Changes

Before opening a pull request:

1. Run the application locally, where possible.
2. Test the functionality you modified.
3. Check that existing features still work.
4. Review your changes for unintended modifications.
5. Make sure you have not included credentials or other sensitive information.

If your contribution includes tests, run the relevant tests and report the results.

Do not claim that a test passed if you did not run it.

9. Commit and Push Your Changes

Review your changes:

git status
git diff

Stage the files you want to include:

git add .

Create a descriptive commit:

git commit -m "Describe your change"

Push your branch to your fork:

git push -u origin feature/your-change

Replace "feature/your-change" with the actual name of your branch.

10. Open a Pull Request

Once your changes are pushed:

1. Open your fork on GitHub.

2. Select Contribute or Compare & pull request, if available.

3. Choose the option to compare across forks if necessary.

4. Configure the pull request as follows:
  
   - Base repository: "elspanish/KelDev"
   - Base branch: "staging"
   - Head repository: "YOUR-USERNAME/KelDev"
   - Compare branch: your contribution branch.

5. Write a clear title and describe your changes.

6. Explain how you tested them.

7. Submit the pull request for review.

Make sure the base branch is "staging", not "main".

Your pull request proposes changes. It does not automatically publish them to the live application.

Pull Request Description

Use this template when submitting your contribution:

What does this PR change?

Describe the changes you made.

Why is this change needed?

Explain the problem it solves or the improvement it introduces.

How was it tested?

Describe the tests you performed and their results.

Additional notes

Mention any limitations, relevant screenshots, or follow-up work.

11. Review Process

The maintainer will review your pull request and may ask for changes.

You may be asked to explain your implementation, fix bugs, add tests, improve documentation, or resolve conflicts.

If changes are requested, make them on the same branch and push them to your fork. GitHub will automatically update the existing pull request.

Contributions may be accepted, returned for revision, or declined if they do not meet the project's requirements.

12. How Changes Reach the Live Platform

KelDev uses two main branches:

- "staging": the integration branch for contributions to the platform.
- "main": the branch used by the live application.

Contributions are reviewed and tested before they are considered ready for release. The maintainer manages the integration of approved changes into "main".

Do not submit platform-development pull requests directly to "main".

13. Responsible Contributions

- Never publish credentials or private user data.
- Do not intentionally introduce vulnerabilities or malicious code.
- Do not make destructive database changes without explicit approval.
- Do not modify production configuration as part of an ordinary contribution.
- Report security vulnerabilities privately to the maintainer rather than publishing exploitable details.

Thank You!

KelDev grows through collaboration.

Whether you fix a small bug, improve the documentation, or implement a new feature, your contribution helps make the platform better.

Find a task, build something useful, and help us improve KelDev together! 
