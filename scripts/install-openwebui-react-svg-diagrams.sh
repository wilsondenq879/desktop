#!/bin/zsh
# Installs the local React + SVG diagram renderer into a self-hosted Open WebUI
# frontend. Pass the open_webui Python-package directory as the first argument.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  print -u2 'Usage: install-openwebui-react-svg-diagrams.sh /path/to/site-packages/open_webui'
  exit 64
fi

script_dir=${0:A:h}
project_dir=${script_dir:h}
target_root=${1:A}
static_dir=${target_root}/frontend/static
public_static_dir=${target_root}/static
index_file=${target_root}/frontend/index.html
version_file=${target_root}/frontend/_app/version.json

if [[ ! -d ${static_dir} || ! -d ${public_static_dir} || ! -f ${index_file} ]]; then
  print -u2 "Open WebUI frontend was not found under: ${target_root}"
  exit 66
fi

install -m 0644 "${project_dir}/node_modules/react/umd/react.production.min.js" "${static_dir}/openwebui-react-18.min.js"
install -m 0644 "${project_dir}/node_modules/react-dom/umd/react-dom.production.min.js" "${static_dir}/openwebui-react-dom-18.min.js"
install -m 0644 "${project_dir}/resources/openwebui-react-svg-diagram-renderer.js" "${static_dir}/openwebui-react-svg-diagram-renderer.js"
install -m 0644 "${project_dir}/node_modules/react/umd/react.production.min.js" "${public_static_dir}/openwebui-react-18.min.js"
install -m 0644 "${project_dir}/node_modules/react-dom/umd/react-dom.production.min.js" "${public_static_dir}/openwebui-react-dom-18.min.js"
install -m 0644 "${project_dir}/resources/openwebui-react-svg-diagram-renderer.js" "${public_static_dir}/openwebui-react-svg-diagram-renderer.js"

if ! rg -q 'openwebui-react-svg-diagram-renderer\.js' "${index_file}"; then
  cp "${index_file}" "${index_file}.before-react-svg-diagrams"
  perl -0pi -e 's{(<script src="/static/loader\.js" defer crossorigin="use-credentials"></script>)}{$1\n\t\t<script src="/static/openwebui-react-18.min.js" defer crossorigin="use-credentials"></script>\n\t\t<script src="/static/openwebui-react-dom-18.min.js" defer crossorigin="use-credentials"></script>\n\t\t<script src="/static/openwebui-react-svg-diagram-renderer.js" defer crossorigin="use-credentials"></script>}' "${index_file}"
fi

# A versioned URL forces iOS WKWebView and installed desktop clients to fetch
# the corrected renderer instead of reusing an older cached response.
perl -0pi -e 's{/static/openwebui-react-svg-diagram-renderer\.js(?:\?v=[^"'"'"']*)?}{/static/openwebui-react-svg-diagram-renderer.js?v=20261016-1}g' "${index_file}"

# SvelteKit clients poll this file to detect a new frontend build. Preserve
# the upstream build ID so the new release is identifiable after injection.
if [[ -f ${version_file} ]]; then
  [[ -f ${version_file}.before-react-svg-diagrams ]] || cp "${version_file}" "${version_file}.before-react-svg-diagrams"
  perl -0pi -e 's{("version"\s*:\s*")([^"]+?)(?:-diagram-v[0-9]+)?(")}{$1.$2."-diagram-v6".$3}ge' "${version_file}"
fi

print "Installed React + SVG diagram renderer in ${target_root}/frontend"
