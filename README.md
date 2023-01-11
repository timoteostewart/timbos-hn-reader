# Timbo’s “Hacker News” Reader

Timbo's Hacker News Reader (THNR) presents the stories posted to [Hacker News](https://news.ycombinator.com/) in what I think is a more informative and enjoyable way.
My core philosophy is to help users be more informed about what each linked story/article offers, so their decisions about which stories to click into are made with greater confidence and efficiency.

This repo is what generates the content for [https://dev.thnr.net/](https://dev.thnr.net/). (Note: At present. thnr.net simply redirects to dev.thnr.net.)

Major features:
- Thumbnails are produced for all linked articles that have an og:image.
    - For linked pages that have an animation as its og:image, the first frame is extracted and used as the thumbnail.
    - Thumbnails are cropped to a pleasant 3:1 rectangular ratio in many cases.
- For most linked articles, the estimated reading time in minutes is calculated and displayed.
- For Github projects, the percentages of programming languages are displayed.
- For PDFs:
    - An image of the first page is displayed as the thumbnail (with a dogear to cue that it's a page).
    - The page count of the PDF is displayed.
    - If the story submitter didn't include "[PDF]" in the title, this tag is added after the anchor text.
- The badges Ⓣ Ⓝ Ⓑ Ⓐ Ⓒ are displayed next to stories that also appear in [topstories.json](https://hacker-news.firebaseio.com/v0/topstories.json) (a.k.a. [/news](https://news.ycombinator.com/news)), [newstories.json](https://hacker-news.firebaseio.com/v0/newstories.json) (a.k.a. [/newest](https://news.ycombinator.com/newest)), [/best](https://news.ycombinator.com/best), [/active](https://news.ycombinator.com/active), and [/classic](https://news.ycombinator.com/classic) to indicate which stories may be trending in multiple HN channels.
- The author's name and channel details (if applicable) are displayed for several of the most popular social media and news websites.
- For Wikipedia articles, the exact name of the linked article is also displayed, not only the (possibly editorialized) title provided by the story's submitter.
- The time since the story was submitted is displayed to the nearest ¼ hour or ½ day.
- A basic dark mode is provided.

# Screenshots

<img src="./gh_screenshots/s-comp.png" width="1000" />



# Additional implementation details

- Extracting information from linked stories and generating pages of HTML is performed multithreaded with a configurable number of workers (`config.max_workers`)
- Story metadata is cached locally to avoid repeated trips to firebase.io endpoints or linked stories.
- Some websites show up on HN a lot and usually have the same og:image, so THNR can be configured to use a substitute (what I call a prepared thumbnail) for a website's og:image. This saves the time that would have been spent retrieving and processing the same og:image repeatedly over time. These prepared thumbnails are in `./prepared_thumbs`.
- Where possible, only the HTTP headers for Web content are retrieved to cut down on THNR's bandwidth usage.
- Reliability is built in several places, from multiple retries when making HTTP requests, to falling back to a minimal story card when the linked article can't be accessed at all, to use of `try/except` in many situations.
- Copious logging throughout to facilitate troubleshooting.
- A conscientious effort has been made to parse the linked article's domain name in such a way that I can serve a link to HN's search engine results of other story submissions to the same domain. For example, sometimes (e.g., [youtube.com](https://news.ycombinator.com/from?site=youtube.com)) HN uses just the domain part of the URL as the key, and other times (e.g., for [github.com](https://news.ycombinator.com/from?site=github.com) and [medium.com](https://news.ycombinator.com/from?site=medium.com)) HN includes the the name/handle/channel from the URL's path as part of the key.



# Setup and installation

I run THNR in a Ubuntu 22.04 container, and the installation notes reflect that context.

## Services and API keys

For its current full functionality, THNR needs:
- an AWS role to access AWS services (see next line)
- read/write permissions to an S3 bucket to publish thumbnails and html pages and to save and retrieve story rosters
- a Google API key to retrieve YouTube video metadata

I also activate a VPN in the container where THNR lives as a simple privacy measure to protect my home's IP address, but a VPN is not required.


## Software dependencies

- Python 3 with `pip`
- Ghostscript
- ImageMagick (see below)
- Chromium and chromedriver (see below)
- Python `Wand` dependencies (see below)

### ImageMagick

#### *IM's version and webp support*

THNR requires ImageMagick with webp read/write support.
You can check for webp support in your install of IM using `identify -list format` (versions <7) or `magick identify -list format` (versions 7+) and examining the line starting `WEBP`.
In Ubuntu 22.04, `sudo apt-get install -y imagemagick` gets you IM version 6.9.11-60 Q16 with webp support of `rw+` which means read, write, and multiframe (i.e., animation) support.
I assume `WEBP` support of `rw-` will also work except for being able to deal with webp animations.

If your install of IM doesn't have webp support, a way forward is to first [build `libwebp` from source](https://developers.google.com/speed/webp/docs/compiling) and then [build ImageMagick from source](https://github.com/ImageMagick/ImageMagick/blob/main/Install-unix.txt) (so that it will include webp support).
I have a publicly available [convenience script i-imagemagick-from-source.sh](https://github.com/timoteostewart/convenience-scripts-to-share/blob/main/i-imagemagick-from-source.sh) to do exactly this, which you are welcome to use.

Please also note that you may wish to install ImageMagick late in the setup/install process, since sometimes other dependencies sneakily install ImageMagick on their own, and you wouldn't want to take the trouble to build IM from source early on only to find out later that your IM install is no longer the default version.

#### *IM's PDF functionality*

If you want THNR to be able to rasterize PDFs as thumbnails, ImageMagick must have permission to work with PDF files.
By default in many IM installations, IM's policy.xml file assigns `rights="none"` (i.e., no permissions) to Ghostscript-related image types.
In policy.xml, either delete the lines shown below or change their `rights` attribute to `read` to allow THNR (via `Wand`) to work with PDFs.

```
<!-- disable ghostscript format types -->
<policy domain="coder" rights="none" pattern="PS" />
<policy domain="coder" rights="none" pattern="PS2" />
<policy domain="coder" rights="none" pattern="PS3" />
<policy domain="coder" rights="none" pattern="EPS" />
<policy domain="coder" rights="none" pattern="PDF" />
<policy domain="coder" rights="none" pattern="XPS" />
```

#### *IM's resource limits*
You might also consider increasing the resource limits in policy.xml while you're there. Here's my entire policy.xml:

```
<policymap>
    <policy domain="resource" name="area" value="999MP"/>
    <policy domain="resource" name="disk" value="8GiB"/>
    <policy domain="resource" name="file" value="768"/>
    <policy domain="resource" name="height" value="999KP"/>
    <policy domain="resource" name="map" value="4GiB"/>
    <policy domain="resource" name="memory" value="4GiB"/>
    <policy domain="resource" name="temporary-path" value="/tmp"/>
    <policy domain="resource" name="thread" value="16"/>
    <policy domain="resource" name="throttle" value="0"/>
    <policy domain="resource" name="width" value="999KP"/>
</policymap>
```

### Chromium and chromedriver

Ensure that your versions of chromedriver and Chrome/Chromium are the same.

Download chromedriver here: https://chromedriver.storage.googleapis.com/index.html

Download Chrome for Linux here: https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

In `settings.yaml`, set `PATH_TO_CHROMEDRIVER` and `PATH_TO_CHROME_BROWSER` to the paths to your chromedriver and Chrome/Chromium browser binaries:


### Python `Wand` dependencies

Wand requires this library:

```bash
sudo apt-get install -y libmagickwand-dev
```


## Installation

1. If you keep the AWS S3 plumbing in THNR, don't forget to update your `~/.aws/credentials` with a role that has appropriate S3 permissions on your AWS account. Set `my_secrets.AWS_PROFILE_NAME` to the name of this role so `boto3` in `aws_utils.py` can find it.

2. Clone the repo. Here's what that looks like for me.

```bash
sudo mkdir /srv/timbos-hn-reader
sudo chown tim:tim /srv/timbos-hn-reader
cd /srv
gh auth login
gh repo clone timoteostewart/timbos-hn-reader
```

3. Create a virtual environment.

```bash
cd /srv/timbos-hn-reader
python -m venv .venv
. ./.venv/bin/activate
```

4. Install Python requirements.

`requirements.txt` should be up to date in the repo, but here is a `pip install` version too:

```bash
pip install wheel beautifulsoup4 boto3 goose3 PyPDF2 python-magic pytz PyYAML requests undetected_chromedriver urllib3 Wand
```

5. I install ImageMagick at this point. You can also simply verify that your installation meets the requirements mentioned earlier.

6. (Optional) Setup `cron` jobs.

I've automated the running of this program on my server. I have these jobs in root's crontab:

```bash
@reboot /srv/timbos-hn-reader/loop-thnr.sh
@daily /srv/timbos-hn-reader/midnight_maint.sh
@reboot /usr/bin/nordvpn connect
```

`loop-thnr.sh` just loops endlessly (with an exit condition if the VPN goes down).



## Command-line invocation

First activate the virtual environment.

Then run the program with `python main.py STORY_TYPE SERVER_NAME SETTINGS_FILE`,
where `STORY_TYPE` is one of `{"active", "best", "classic", "new", "top"}`,
`SERVER_NAME` is represented in the `settings.yaml` file,
and `SETTINGS_FILE` is a path to a valid yaml file with the appropriate fields and hierarchy.

Here's what this looks like for me:

```bash
. ./.venv/bin/activate
python main.py new thnr /srv/timbos-hn-reader/settings.yaml
```



# Roadmap
- implement a Bloom filter to more performantly identify URLs that have a prepared thumbnail
- minify CSS files and generated HTML to decrease both load times and bandwidth usage
- change THNR's internal story caching model from `pickle`s to JSON
- show the duration of linked YouTube videos in hh:mm:ss format
- add more social media processors for story links to popular domains (using [https://hackernews-insight.vercel.app/domain-analysis](https://hackernews-insight.vercel.app/domain-analysis) as a guide to which ones to work on next)
- organize settings in `settings.yaml` or `config.py` more sanely
- add support for HN polls
- add dedicated feeds for Ask HN, Show HN, and jobs
- also see issues tagged [performance](https://github.com/timoteostewart/timbos-hn-reader/issues?q=is%3Aissue+is%3Aopen+label%3Aperformance) and [enhancement](https://github.com/timoteostewart/timbos-hn-reader/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)



# Contributions
Fork away, please! Comments, suggestions, and [bug reports](https://github.com/timoteostewart/timbos-hn-reader/issues) are also all welcome.

One of my aims with the THNR project is to try new things out for myself and follow where my curiosity and changing coding interests take me, so please be aware that I might accept some pull requests and not others.
At this time I'm far more likely to accept a friendly and small bug PR than a significant new feature branch, for example.


# License

Timbo's Hacker News Reader is MIT licensed, as found in the LICENSE file.



