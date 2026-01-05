# Ecosystems Evaluate - Analysis Viewer

Interactive Vue.js web application for visualizing dependency analysis results.

## Features

- 📊 **Interactive Charts** - Visualize dependencies and coverage with Chart.js
- 🔍 **Search & Filter** - Find projects and dependencies quickly
- 📈 **Coverage Analysis** - View Chainguard package availability
- 🎯 **Adoption Tracking** - See which projects use Chainguard packages

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production (outputs to /docs for GitHub Pages)
npm run build
```

## Usage

1. Run analysis with the CLI tool:
   ```bash
   python3 main.py -O analysis.json --coverage -v
   ```

2. Open the viewer:
   - **Local development**: `npm run dev` then upload `analysis.json`
   - **GitHub Pages**: Visit the deployed site and upload your file

## Deployment to GitHub Pages

```bash
# Build the static site
npm run build

# Commit the docs/ folder
git add docs/
git commit -m "Build viewer for GitHub Pages"
git push

# Enable GitHub Pages in repo settings:
# Settings → Pages → Source: Deploy from branch → Branch: main → Folder: /docs
```

## Project Structure

```
viewer/
├── src/
│   ├── App.vue              # Main app component
│   ├── main.js              # Entry point
│   ├── style.css            # Global styles
│   └── components/
│       ├── Overview.vue     # Overview tab
│       ├── Stats.vue        # Charts and statistics
│       ├── Projects.vue     # Projects table
│       └── Dependencies.vue # Dependencies list
├── index.html               # HTML template
└── README.md                # This file
```

## Tech Stack

- **Vue 3** - Reactive UI framework
- **Vite** - Fast build tool
- **Chart.js** - Data visualization
- **vue-chartjs** - Vue wrapper for Chart.js
