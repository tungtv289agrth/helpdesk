<div align="center" markdown="1">

<img src=".github/hd-logo.svg" alt="Frappe Helpdesk logo" width="80"/>
<h1>Frappe Helpdesk</h1>

**Customer Service, Made Simple and Effective**

![GitHub release (latest by date)](https://img.shields.io/github/v/release/frappe/helpdesk)
[![codecov](https://codecov.io/github/frappe/helpdesk/branch/develop/graph/badge.svg?token=8ZXHCY4G9U)](https://codecov.io/github/frappe/helpdesk)

<a href="https://trendshift.io/repositories/12764" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12764" alt="teableio%2Fteable | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

</div>


<div align="center">
	<img src="./.github/Hero2.png" alt="Hero Image" width="100%" />
</div>
<br />
<div align="center">
	<a href="https://frappe.io/helpdesk">Website</a>
	-
	<a href="https://docs.frappe.io/helpdesk">Documentation</a>
</div>

## Frappe Helpdesk
Frappe Helpdesk is an 100% open-source Ticket Management tool which helps you  streamline your company's support, offers an easy setup, clean user interface, and automation tools to resolve customer queries efficiently.



### Motivation
Managing issues from our customers was a big challenge for us. We were using the ERPNext support module which was not very good in UI and the UX was also not good. We wanted to have a tool that can be easily integrated with our existing system and can be customized as per our needs. So we decided to build Frappe Helpdesk.

### Key Features

- **Agent and Customer Portal Views**: Dual portals for agents and customers to simplify issue submission and management.

- **Customizable SLAs**: Discover how you can set and track SLAs for better response times.

- **Assignment Rules**: Custom auto-assignment of tickets based on priority, issue type, or workload.

- **Knowledge Base**: Learn how to create and manage help articles to empower users and reduce tickets.

- **Saved Replies**: Pre-written replies for common queries to ensure quick and consistent communication.

<details open>
<summary >View Screenshots</summary>
<h3></h3>

<div align="center">
	<sub>
		Agent List View
	</sub>
</div>

![Agent List View](.github/AgentListView.png)


<div align="center">
	<sub>
		Upload articles and let your customer solve their queries through the Knowledge Base.
	</sub>
</div>

![Knowledge Base](.github/KB.png)

<div align="center">
	<sub>
		With advanced search, your customers will be recommended relevant articles regarding their issue.
	</sub>
</div>


![Article Search](.github/Search2.png)



</details>
<br>


### Under the Hood

- [**Frappe Framework**](https://github.com/frappe/frappe): A full-stack web application framework written in Python and Javascript.

- [**Frappe UI**](https://github.com/frappe/frappe-ui): A Vue-based UI library, to provide a modern user interface. 


## Production Setup

### Managed Hosting

You can try [Frappe Cloud](https://frappecloud.com), a simple, user-friendly and sophisticated [open-source](https://github.com/frappe/press) platform to host Frappe applications with peace of mind.

It takes care of installation, setup, upgrades, monitoring, maintenance and support of your Frappe deployments. It is a fully featured developer platform with an ability to manage and control multiple Frappe deployments.

<div>
	<a href="https://frappecloud.com/helpdesk/signup" target="_blank">
		<picture>
			<source media="(prefers-color-scheme: dark)" srcset="https://frappe.io/files/try-on-fc-white.png">
			<img src="https://frappe.io/files/try-on-fc-black.png" alt="Try on Frappe Cloud" height="28" />
		</picture>
	</a>
</div>

### Self Hosting

Follow these steps to set up Frappe Helpdesk in production:

**Step 1**: Download the easy install script

```bash
wget https://frappe.io/easy-install.py
```

**Step 2**: Run the deployment command

```bash
python3 ./easy-install.py deploy \
    --project=helpdesk_prod_setup \
    --email=your_email.example.com \
    --image=ghcr.io/frappe/helpdesk \
    --version=stable \
    --app=helpdesk \
    --sitename subdomain.domain.tld
```

Replace the following parameters with your values:
- `your_email.example.com`: Your email address
- `subdomain.domain.tld`: Your domain name where Helpdesk will be hosted

The script will set up a production-ready instance of Frappe Helpdesk with all the necessary configurations in about 5 minutes.

## Development Setup

### Docker

You need Docker, docker-compose and git setup on your machine. Refer [Docker documentation](https://docs.docker.com/). After that, follow below steps:

**Step 1**: Setup folder and download the required files

    mkdir frappe-helpdesk
    cd frappe-helpdesk

    # Download the docker-compose file
    wget -O docker-compose.yml https://raw.githubusercontent.com/frappe/helpdesk/develop/docker/docker-compose.yml

    # Download the setup script
    wget -O init.sh https://raw.githubusercontent.com/frappe/helpdesk/develop/docker/init.sh

**Step 2**: Run the container and daemonize it

    docker compose up -d

**Step 3**: The site [http://helpdesk.localhost:8000/helpdesk](http://helpdesk.localhost:8000/helpdesk) should now be available. The default credentials are:
- Username: Administrator
- Password: admin

### Local

To setup the repository locally follow the steps mentioned below:

1. Install bench and setup a `frappe-bench` directory by following the [Installation Steps](https://frappeframework.com/docs/user/en/installation)
1. Start the server by running `bench start`
1. In a separate terminal window, create a new site by running `bench new-site helpdesk.test`
1. Map your site to localhost with the command `bench --site helpdesk.test add-to-hosts`
1. Get the Telephony app. Run `bench get-app https://github.com/frappe/telephony`
1. Get the Helpdesk app. Run `bench get-app https://github.com/frappe/helpdesk`
1. Run `bench --site helpdesk.test install-app helpdesk`.
1. Run `bench build --app helpdesk`
1. Now open the URL `http://helpdesk.test:8000/helpdesk` in your browser, you should see the app running


**For Frontend Development**
1. Open a new terminal session and cd into `frappe-bench/apps/helpdesk/desk`, and run the following commands:
    ```
    yarn install
    yarn dev or yarn dev --host helpdesk.test
    ```
1. Now, you can access the site on vite dev server at `http://helpdesk.test:8080`

**Note:** You'll find all the code related to Helpdesk's frontend inside `frappe-bench/apps/helpdesk/desk`

## AI Summary — "Tải file lên" (Auto-fill ticket title & description)

On the *New Ticket* page a floating button (**Tải file lên**) lets users pick
a file (invoice, screenshot, document…). The system reads the file, asks an
LLM for a short title and description, then auto-fills the **Tiêu đề**, **Mô
tả** and **Đính kèm** fields. It is an optional shortcut — the regular manual
flow is unchanged, and a user who already typed a title/description is never
overwritten.

### Python dependencies

Installed from `pyproject.toml` (`pip install -e .` / `bench setup requirements`):
`pymupdf`, `mammoth`, `pandas`, `pytesseract`, `pdf2image`,
`opencv-python-headless`, `sumy`.

### OS-level packages (required — cannot be installed via pip)

These must be installed at the operating system level or the pipeline fails:

```bash
# Debian / Ubuntu
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-vie \
    poppler-utils
```

- `tesseract-ocr` + `tesseract-ocr-vie`: OCR for scanned PDFs and images
  (Vietnamese language pack).
- `poppler-utils`: provides `pdftoppm`, required by `pdf2image`.

### Configuration (`site_config.json`)

The API key and model are **never hardcoded** — they are read from
`sites/<site>/site_config.json`:

```json
{
  "ai_summary_llm_api_key": "AIza...",
  "ai_summary_llm_model": "gemini-2.5-flash",
  "ai_summary_max_files_per_call": 3,
  "ai_summary_max_file_size_mb": 15,
  "ai_summary_rate_limit_per_user": 15,
  "ai_summary_rate_limit_window_minutes": 10
}
```

Do not commit the API key. The provider is the Google Gemini API
(`generateContent`); the `...` in `ai_summary_llm_api_key` must be replaced
with a valid key from <https://aistudio.google.com/apikey> and
`ai_summary_llm_model` with a valid Gemini model id (e.g. `gemini-2.5-flash`).

### How it works (synchronous, bounded)

1. **App Guard** — file-type whitelist (pdf, docx, xlsx, csv, txt/md, png,
   jpg/jpeg), ≤ 15 MB/file, ≤ 3 files/call, and a per-user Redis rate limit
   (default 15 calls / 10 minutes). Violations stop here, before any LLM call.
2. **Convert to text** — PDF (PyMuPDF), DOCX (mammoth), XLSX/CSV (pandas,
   first 20 rows), TXT/MD direct; scans & images go through Tesseract OCR
   (first page only). Each conversion has a 10s timeout.
3. **Compress** — text over 3.000 chars/file or 10.000 chars total is reduced
   with `sumy` (TextRank) instead of being cut.
4. **LLM** — only plain text is sent to Google Gemini (10s timeout); the result is a
   title (≤ 80 chars) + description (≤ 400 chars) or a
   `not_enough_information` / `irrelevant_content` reason.


## Compatibility matrix 

| Helpdesk Branch | Compatible Frappe Framework Version |
|-----------------|-------------------------------------|
| main            | version-15                          |
| main            | version-16                          |
| develop         | develop branch                      |


## Learn and connect

- [Telegram Public Group](https://t.me/frappedesk)
- [Discuss Forum](https://discuss.frappe.io/c/frappehelpdesk/69)
- [Documentation](https://docs.frappe.io/helpdesk)

## Contributing

1. [Issue Guidelines](https://github.com/frappe/erpnext/wiki/Issue-Guidelines)
1. [Report Security Vulnerabilities](https://frappe.io/security)
1. [Pull Request Requirements](https://github.com/frappe/erpnext/wiki/Contribution-Guidelines)
2. [Translations](https://crowdin.com/project/frappe)

<br>
<br>
<div align="center">
	<a href="https://frappe.io" target="_blank">
		<picture>
			<source media="(prefers-color-scheme: dark)" srcset="https://frappe.io/files/Frappe-white.png">
			<img src="https://frappe.io/files/Frappe-black.png" alt="Frappe Technologies" height="28"/>
		</picture>
	</a>
</div>
