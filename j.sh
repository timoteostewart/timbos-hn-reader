#!/bin/bash

temp_dir_root="/mnt/synology/temp/transfer_to_thnr3"
dest_dir_root="/srv/timbos-hn-reader"

dirs_to_copy=(
    cached_stories
    completed_pages
    css_files
    logs
    prepared_thumbs
    templates
)

for dir in "${dirs_to_copy[@]}"; do
    cp --recursive --update --verbose "${temp_dir_root}/${dir}" "${dest_dir_root}"
done
