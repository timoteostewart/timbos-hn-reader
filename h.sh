#!/bin/bash

dirs_needed=(
    cached_stories
    completed_pages
    css_files
    logs
    prepared_thumbs
    templates
)

for dir in "${dirs_needed[@]}"; do
    mkdir --parents "/srv/timbos-hn-reader/$dir"
done

