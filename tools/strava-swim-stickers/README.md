# Strava swim stickers

Exports a transparent 1080×1920 PNG (distance, time, pace /100m) for every
Strava swim in the last N days (99 by default), ready for Instagram Stories.

Strava's API doesn't expose the in-app "Share Activity" images, so the script
reads each swim through the API and renders an equivalent sticker.

## One-time setup

1. Create an API app at <https://www.strava.com/settings/api>.
   Set **Authorization Callback Domain** to `localhost`.
2. Get a refresh token with access to all activities, including private ones:

   ```sh
   pip install pillow
   python strava_swim_stickers.py auth --client-id <ID> --client-secret <SECRET>
   ```

## Run it

**On GitHub:** add `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` and
`STRAVA_REFRESH_TOKEN` as repository secrets. Then go to Actions →
*Strava swim stickers* → *Run workflow*. Download the PNG zip from the run's
**Artifacts** section.

**Locally:**

```sh
export STRAVA_CLIENT_ID=... STRAVA_CLIENT_SECRET=... STRAVA_REFRESH_TOKEN=...
python strava_swim_stickers.py export --days 99 --out swims
```

On a Mac, add `--import-to-photos` to also put the stickers in a Photos album
called "Strava Swims" (change it with `--album`). With iCloud Photos on, they
sync to your iPhone, ready for Instagram Stories. macOS asks once for permission
to control Photos. Re-runs only import swims that aren't already in `--out`.

Files are named `YYYY-MM-DD_<activity id>_<name>.png`. Use `--font path/to/font.ttf`
to pick another font. By default it uses Montserrat Bold when installed.
