# scrapeBot

Checks ikman.lk Colombo room & annex rentals every hour and emails you new ads that:

- cost **Rs 30,000 ≤ rent < Rs 40,000** per month
- do **not** mention ladies / girls / female / women (English or Sinhala) in the title or description
- were posted since the previous run

It runs for free on GitHub Actions. Criteria live in [config.yaml](config.yaml).

## How it works

1. Reads the search results page (newest first). ikman embeds the ad data as JSON in
   `window.initialData`, so no browser is needed.
2. Keeps ads that are not in `state/seen.json` and were created in the last 24 hours
   (an ad's creation time is encoded in its ID).
3. Checks price and title, then opens the ad page to check the full description.
4. Emails all matches in one message, then records them in `state/seen.json`, which the
   workflow commits back to the repo.

The very first run only records the current ads, without emailing, so you are not
flooded with old listings.

## Setup

### 1. Gmail App Password
1. Turn on 2-Step Verification for your Google account.
2. Go to <https://myaccount.google.com/apppasswords>, create an app password named
   `scrapeBot`, and copy the 16-character password.

### 2. GitHub repository
1. Create a new **private** repository on GitHub and push this folder to it.
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `SMTP_USER`: your Gmail address
   - `SMTP_PASSWORD`: the app password from step 1
   - `EMAIL_TO`: where alerts go (optional; defaults to `SMTP_USER`; comma-separate several)
3. **Actions** tab → *ikman room alert* → **Run workflow**, tick **Only send a test email**,
   and run it. You should get an email titled "ikman bot: test email". If the run fails,
   check the secrets.
4. **Run workflow** again with the box unticked to do the first real run.

After that it runs every hour by itself (GitHub may start scheduled runs a few minutes late).
Hourly runs use about 720 of the 2,000 free Actions minutes per month on a private repo.

If a run fails (for example ikman changes its page layout), GitHub emails the repo owner.

## Run locally

```bash
pip install -r requirements.txt
python main.py --dry-run --ignore-seen --lookback-hours 72
```

`--dry-run` prints what would be emailed without sending anything or touching the state file.
To test the email for real, set `SMTP_USER`, `SMTP_PASSWORD` (and optionally `EMAIL_TO`)
as environment variables and run `python main.py --test-email`.

## Notes

- GitHub pauses scheduled workflows after 60 days without commits. The bot's own
  `seen.json` commits normally keep it active; if it is ever paused, re-enable it from the
  Actions tab.
- Keep the frequency low (hourly is fine). This is for personal use; respect ikman's terms.
