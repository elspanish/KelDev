Contributing to KelDev

Thanks for helping improve KelDev! Every contribution counts, whether it's fixing a bug, improving the UI, or adding a feature.

1. Set Up

You'll need Python, Git, and a GitHub account.

Fork this repository on GitHub, then clone your fork:

git clone https://github.com/YOUR-USERNAME/KelDev.git
cd KelDev

Create a branch for your changes:

git switch -c feature/your-change

Install the dependencies:

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

2. Configure & Run

Copy "pcapp/.env.example" to "pcapp/.env" and add the credentials required for your task. The application uses Supabase and may require Groq or Gemini API keys.

Never commit your ".env" file or share your API keys.

Run KelDev:

streamlit run pcapp/main.py

3. Make Your Contribution

Work on your branch, keep your changes focused, and test them before submitting.

Commit and push your changes:

git add .
git commit -m "Describe your change"
git push -u origin feature/your-change

4. Open a Pull Request

On GitHub, open a pull request with these settings:

- Base repository: "elspanish/KelDev"
- Base branch: "staging"
- Compare branch: your branch in your fork.

Explain what you changed and how you tested it.

Important: Submit platform contributions to "staging", not "main". Changes are reviewed before reaching the live application.

That's it! Thanks for contributing to KelDev. 
