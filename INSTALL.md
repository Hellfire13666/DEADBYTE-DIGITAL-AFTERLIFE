# ☠ DEADBYTE // DIGITAL AFTERLIFE
## INSTALL THE REAPER DECK

**GitHub:** https://github.com/Hellfire13666/DEADBYTE-DIGITAL-AFTERLIFE

**DEADBYTE** is a local Linux terminal research suite for historical archives, vintage newspapers, public records, geo-storm intelligence and privately saved research sessions.

> **DIG UP THE PAST. RESURRECT THE RECORD.**  
> One-word launch: `deadbyte`. No public hosting or browser automation required.

### ☣ Before installing

- Linux with Python 3, Git, a POSIX-compatible `sh` and the `install` utility
- Internet access for live archive and weather-provider searches
- Access to this GitHub repository. **While it remains private, only authorized GitHub accounts can clone it.**
- A **new** DEADBYTE installation. The installer is not an updater and deliberately refuses to overwrite an existing app or local evidence vault.

No `sudo` is required. The installer places files under `$HOME/.local/`, using the current user's home directory.

### 01 // CLONE THE REAL GITHUB REPOSITORY

Open a terminal in a directory where you want to keep the source checkout:

```sh
git clone https://github.com/Hellfire13666/DEADBYTE-DIGITAL-AFTERLIFE.git
cd DEADBYTE-DIGITAL-AFTERLIFE
```

**Private repository note:** GitHub may require existing Git credentials, a credential manager, or a browser-based login. Never put credentials or tokens in a command you share publicly. If Git responds `Repository not found` or `403`, first confirm that the signed-in GitHub account has access. Do not assume the repository is public.

### 02 // INSTALL THE REAPER DECK

From the root of the cloned repository, run:

```sh
sh install.sh
```

The script installs the main terminal application and seven research modules, the local `deadbyte` starter command and the HEXCODEX guest-recipes page. It checks for an existing installation **before** copying files and stops rather than overwriting your private work.

Expected completion text:

```text
DEADBYTE // FILES INSTALLED
START COMMAND // deadbyte
```

If you see `STOP // Existing DEADBYTE files detected`, **do not delete your old installation or vault** just to force the installer to run. This package is intended for fresh installations, not upgrades.

### 03 // ONE-WORD LAUNCH

```sh
deadbyte
```

If your shell reports `command not found`, add the standard local executable directory to **the current terminal session** and retry:

```sh
export PATH="$HOME/.local/bin:$PATH"
deadbyte
```

Your shell's persistent PATH configuration may differ. The installation itself does not rewrite shell startup files.

### 04 // OPEN THE RECIPES

The companion offline HTML guide is installed at:

```text
$HOME/.local/share/deadbyte-hexcodex/DEADBYTE-HEXCODEX-GUEST-20-RECIPES.html
```

On a Linux desktop, open it with:

```sh
xdg-open "$HOME/.local/share/deadbyte-hexcodex/DEADBYTE-HEXCODEX-GUEST-20-RECIPES.html"
```

Or view the [HEXCODEX source page](recipes/DEADBYTE-HEXCODEX-GUEST-20-RECIPES.html) in this repository.

### 05 // REAPER DECK RESEARCH BAYS

| Switch | Research module |
|:---:|---|
| 01–05 | Internet Archive, Open Library, Library of Congress, Wikisource and Project Gutenberg |
| 06 | Historical Newspapers |
| 07 | Wayback Machine |
| 08 | Common Crawl |
| 09 | Archive-It |
| 10 | Wikimedia Commons heritage images |
| 11 | Multi-source research |
| 12 | Private DEAD VAULT |
| 13 | Provider Field Notes |
| 14 | DEAD ARCHIVES and historical NOAA storm intelligence |
| 15–16 | Reserved / future bays, not live research engines |

Live provider availability and coverage vary. A timeout isn't proof that an event or source record does not exist. Capture and upload dates are not automatically historical event dates.

### 🔐 PRIVATE DEAD VAULT // NEVER PUBLISH

The research vault stays in the local user account under `$HOME/.local/share/deadbyte`. **Private session data and backups are not shipped with the GitHub source package.** Do not commit your vault JSON, saved results, local configuration or personal logs.

The installer was tested with a disposable home directory and verified to display the main menu and exit. **This is not an assertion that every provider or dependency has been tested on every Linux distribution.** The software code is distributed under [MIT](LICENSE), subject to ownership and third-party rights; historical images and external research records have their own licenses.

---

**☠ DEADBYTE // DIGITAL AFTERLIFE**  
[Repository front page](README.md) · [Reaper Deck showcase](showcase/index.html) · [Privacy information](PRIVACY.md)
