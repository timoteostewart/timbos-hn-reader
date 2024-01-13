import collections
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

import magic
import urllib3
import wand.exceptions
from PyPDF2 import PdfReader, PdfWriter
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image

import aws_utils
import config
import file_utils
import text_utils
import url_utils

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# TODO: change these lookups to use a Bloom filter
prepared_images_roster_by_full_url = {
    "https://149521506.v2.pressablecdn.com/wp-content/uploads/2018/06/seth_godin_ogimages_v02_18061313.jpg": "seths-blog",
    "https://a0.awsstatic.com/libra-css/images/logos/aws_logo_smile_1200x630.png": "aws-logo-smile",
    "https://a0.awsstatic.com/libra-css/images/logos/aws_logo_smile_1200x630.png": "aws-logo-smile",
    "https://cdn.jamanetwork.com/images/logos/JAMA.png": "jama-network",
    "https://developer.mozilla.org/mdn-social-share.cd6c4a5a.png": "mdn-web-docs",
    "https://github.githubassets.com/images/modules/gists/gist-og-image.png": "github-gist",
    "https://github.githubassets.com/assets/gist-og-image-54fd7dc0713e.png": "github-gist",
    "https://hacks.mozilla.org/files/2022/03/mdnplus.png": "hacks-mozilla",
    # "https://lemire.me/img/portrait2018facebook.jpg": "lemire",
    # "https://lethain.com/static/author.png": "lethain",
    "https://media.npr.org/include/images/facebook-default-wide.jpg?s=1400": "npr-default",
    "https://media.npr.org/include/images/facebook-default-wide-s1400-c100.jpg": "npr-default",
    "https://s1.reutersmedia.net/resources_v2/images/rcom-default.png?w=800": "reuters",
    "https://savo.rocks/assets/img/favicons/favicon.png": "savo",
    "https://static.npmjs.com/338e4905a2684ca96e08c7780fc68412.png": "npmjs",
    "https://static-production.npmjs.com/338e4905a2684ca96e08c7780fc68412.png": "npmjs",
    "https://world.hey.com/dhh/avatar-20210222112907000000-293866624": "dhh",
    "https://world.hey.com/dhh/avatar-df6405b0f7fafda980fd38b04c334bec936aef69": "dhh",
    "https://www.postgresql.org/media/img/about/press/elephant.png": "psql-press",
    "https://www.redditstatic.com/new-icon.png": "new-reddit-icon",
    "https://www.reuters.com/pf/resources/images/reuters/reuters-default.png?d=76": "reuters",
    "https://www.science.org/pb-assets/images/blogs/pipeline/default-image-1644619966880.png": "pipeline",
}

prepared_images_roster_by_substring = {
    "hey.com/dhh/avatar": "dhh",
    "logo_chromium.png": "chromium-logo",
    "media.npr.org/include/images/facebook-default-wide": "npr-default",
    "reuters-default.png": "reuters",
    "reutersmedia.net/resources_v2/images/rcom-default.png": "reuters",
    "seth_godin_ogimages": "seths-blog",
    "hey.com/dhh/avatar": "dhh",
}

domains_exempt_from_trim = ["opengraph.githubassets.com"]

domains_with_higher_quality_resizing = ["opengraph.githubassets.com"]

filename_substrings_making_exempt_from_trim = [
    "flag",
]

ignore_images_whose_urls_contain_these_substrings = [
    "https://www.redditstatic.com/new-icon.png",
]

ignore_images_at_these_urls = [
    "https://pastebin.com/i/facebook.png",
    "https://s0.wp.com/i/blank.jpg",
    "https://assets.msn.com/staticsb/statics/latest/homepage/msn-logo.svg",
]

ignore_images_from_these_domains = []


def sanitize(s: str):
    s = s.lower()
    allowed_chars = "abcdefghijklmnopqrstuvwxyz 0123456789"
    sanitized = ""
    for char in s:
        if char in allowed_chars:
            sanitized += char
    sanitized = re.sub(" {2,}", " ", sanitized)
    return sanitized.strip()


def shortcode_if_og_image_url_contains_certain_substring(og_image_url: str):
    for each_substring in prepared_images_roster_by_substring:
        if each_substring in og_image_url:
            return prepared_images_roster_by_substring[each_substring]
    return None


def get_webp_filename(story_as_object, size):
    return f"thumb-{story_as_object.id}-{size}.webp"


def get_webp_full_save_path(story_as_object, size):
    return os.path.join(
        config.settings["THUMBS_DIR"],
        get_webp_filename(story_as_object, size),
    )


def can_find_a_shortcode(story_as_object, img_loading):
    logger.info(f"id {story_as_object.id}: checking for a shortcode...")
    # check if thumb is already available as prepared image
    prepared_image_shortcode = ""

    if (
        story_as_object.linked_url_og_image_url_final
        in prepared_images_roster_by_full_url
        or story_as_object.linked_url_og_image_url_initial
        in prepared_images_roster_by_full_url
    ):
        prepared_image_shortcode = prepared_images_roster_by_full_url[
            story_as_object.linked_url_og_image_url_final
        ]

    if not prepared_image_shortcode:
        prepared_image_shortcode = shortcode_if_og_image_url_contains_certain_substring(
            story_as_object.linked_url_og_image_url_final
        )

    if prepared_image_shortcode:
        logger.info(
            f"id {story_as_object.id}: using prepared image shortcode {prepared_image_shortcode}"
        )

        # load prepared image for certain size as image
        for each_size in ["medium", "extralarge"]:
            thumb_filename = get_webp_filename(story_as_object, each_size)
            shutil.copyfile(
                os.path.join(
                    config.settings["PREPARED_THUMBS_SERVICE_DIR"],
                    f"prepared-{prepared_image_shortcode}-{each_size}.webp",
                ),
                os.path.join(config.settings["TEMP_DIR"], thumb_filename),
            )
            try:
                aws_utils.upload_thumb(thumb_filename=thumb_filename)
            except Exception as exc:
                logger.error(
                    f"{sys._getframe(  ).f_code.co_name}: "
                    f"id {story_as_object.id}: "
                    f"failed to upload thumb (prepared image) to S3: {exc}"
                )
                return False

            file_utils.delete_file(
                os.path.join(config.settings["TEMP_DIR"], thumb_filename)
            )

        story_as_object.image_slug = create_img_slug_html(story_as_object, img_loading)
        logger.info(
            f"{sys._getframe(  ).f_code.co_name}: "
            f"id {story_as_object.id}: "
            f"using prepared image for image {story_as_object.linked_url_og_image_url_final}"
        )
        return True
    else:
        return False


def create_img_slug_html(story_as_object, img_loading="lazy"):
    return (
        '<div class="thumb">'
        f'<a href="{story_as_object.url}">'
        "<img "
        "srcset="
        f'"{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 4x, '
        f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 3x, '
        f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 2x, '
        f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "medium")} 1x" '
        'sizes="(min-width: 1440px) 350px, (min-width: 1080px) 350px, (min-width: 768px) 350px, 350px" '
        f'src="{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "medium")}" '
        f'alt="{sanitize(story_as_object.title)}" '
        'class="thumb" '
        f'loading="{img_loading}" />'
        "</a>"
        "</div>"
    )


def save_thumb_where_it_should_go(webp_image, story_as_object, size):
    thumb_filename = get_webp_filename(story_as_object, size)
    webp_image.save(filename=os.path.join(config.settings["TEMP_DIR"], thumb_filename))
    try:
        aws_utils.upload_thumb(thumb_filename=thumb_filename)
    except Exception as exc:
        logger.error(
            f"{sys._getframe(  ).f_code.co_name}: "
            f"id {story_as_object.id}: "
            f"failed to upload thumb to S3: {exc}"
        )
        raise exc
    else:
        file_utils.delete_file(
            os.path.join(config.settings["TEMP_DIR"], thumb_filename)
        )


def get_image_slug(story_as_object, img_loading="lazy"):
    # initialize image slug as an empty string
    story_as_object.image_slug = text_utils.EMPTY_STRING
    # bgcolor_as_Color = (None,)
    force_aspect = None
    no_trim = False
    no_pad = False

    # check if we ignore the exact URL
    if story_as_object.linked_url_og_image_url_final in ignore_images_at_these_urls:
        story_as_object.has_thumb = False
        return

    # check if we ignore the exact domain
    _, og_image_domains = url_utils.get_domains_from_url(
        story_as_object.linked_url_og_image_url_final
    )
    if og_image_domains in ignore_images_from_these_domains:
        story_as_object.has_thumb = False
        return

    if can_find_a_shortcode(story_as_object, img_loading):
        return

    ##
    ## resize thumbnails from downloaded og:image
    ##

    # update trim settings, if necessary
    _, og_image_domains = url_utils.get_domains_from_url(
        story_as_object.linked_url_og_image_url_final
    )
    if og_image_domains in domains_exempt_from_trim:
        no_trim = True

    # check if there's a keyword in the image filename that means we don't trim (e.g., "flag")
    magic_result = magic.from_file(
        story_as_object.downloaded_orig_thumb_full_path, mime=True
    )
    if (
        "image" in magic_result
        and "base_name" in story_as_object.thumb_filename_details
    ):
        for pattern in filename_substrings_making_exempt_from_trim:
            if pattern in story_as_object.thumb_filename_details["base_name"].lower():
                logger.info(
                    f"id {story_as_object.id}: will not trim image with base filename {story_as_object.thumb_filename_details['base_name']}"
                )
                force_no_trim = True
                no_trim = True
                break

        for pattern in ignore_images_whose_urls_contain_these_substrings:
            if pattern in story_as_object.thumb_filename_details["base_name"].lower():
                logger.info(
                    f"id {story_as_object.id}: will skip image with base filename {story_as_object.thumb_filename_details['base_name']} since it constains substring {pattern}"
                )
                story_as_object.has_thumb = False
                return

    # initialize webp compression levels from settings
    WEBP_SMALL_THUMB_COMPRESSION_QUALITY = int(
        config.settings["THUMBS"]["COMP_QUAL"]["SMALL"]
    )  # default value
    WEBP_MEDIUM_THUMB_COMPRESSION_QUALITY = int(
        config.settings["THUMBS"]["COMP_QUAL"]["MEDIUM"]
    )  # default value
    # WEBP_LARGE_THUMB_COMPRESSION_QUALITY = int(
    #     config.settings["THUMBS"]["COMP_QUAL"]["LARGE"]
    # )  # default value
    WEBP_EXTRALARGE_THUMB_COMPRESSION_QUALITY = int(
        config.settings["THUMBS"]["COMP_QUAL"]["EXTRALARGE"]
    )  # default value

    # preferentially render thumbs from certain domains with better quality
    if og_image_domains in domains_with_higher_quality_resizing:
        # WEBP_SMALL_THUMB_COMPRESSION_QUALITY = min(
        #     100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 5
        # )
        WEBP_MEDIUM_THUMB_COMPRESSION_QUALITY = min(
            100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 10
        )
        # WEBP_LARGE_THUMB_COMPRESSION_QUALITY = min(
        #     100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 15
        # )
        WEBP_EXTRALARGE_THUMB_COMPRESSION_QUALITY = min(
            100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 20
        )

    # if multipage PDF, keep only first page
    if magic_result == "application/pdf":
        try:
            fix_multipage_pdf(story_as_object)
        except Exception as exc:
            logger.info(
                f"{sys._getframe(  ).f_code.co_name}: "
                f"id {story_as_object.id}: "
                f"problem with pdf; won't use a thumbnail"
            )
            story_as_object.has_thumb = False
            return
        no_pad = True

    try:
        with Image(
            filename=story_as_object.downloaded_orig_thumb_full_path
        ) as downloaded_img:
            image_format = downloaded_img.format

            # if animation, use only first frame
            if image_format in ["GIF", "WEBP"]:
                # TODO: try decomposing the animation to a temp dir using wand/magick's convert -coalesce and grab the first image file (i.e., first frame)
                # reason for the above todo is that Wand keeps choking on 3MB gif animations.
                # or possibly via system call: `convert 'animation.gif[0]' first_frame.png`
                if len(downloaded_img.sequence) > 1:
                    first_frame = downloaded_img.sequence[0]
                    logger.info(
                        f"{sys._getframe(  ).f_code.co_name}: "
                        f"id {story_as_object.id}: "
                        f"used first frame of animation in {story_as_object.downloaded_orig_thumb_filename}"
                    )
                    downloaded_img = Image(image=first_frame)

            # if SVG format, rasterize using Wand
            elif image_format in ["SVG"]:
                try:
                    vec_img = Image(
                        filename=story_as_object.downloaded_orig_thumb_full_path,
                        resolution=600.0,  # 1000.0 might have caused error
                    )
                except Exception as exc:
                    logger.error(
                        (
                            f"{sys._getframe(  ).f_code.co_name}: "
                            f"id {story_as_object.id};"
                            f"SVG filename {story_as_object.downloaded_orig_thumb_full_path};"
                            f"{exc}"
                        )
                    )
                    raise exc
                vec_img.background_color = Color("white")
                vec_img.alpha_channel = "off"
                vec_img.convert("png")
                vec_img.transform(resize=f"3000x")
                downloaded_img = Image(image=vec_img)

            # if PDF format, rasterize using Ghostscript
            elif image_format in ["PDF", "AI"]:
                try:
                    png2pdf_filename_full_path = rasterize_pdf_using_ghostscript(
                        story_as_object
                    )
                    story_as_object.downloaded_orig_thumb_full_path = (
                        png2pdf_filename_full_path
                    )
                    # print(story_as_object.downloaded_orig_thumb_full_path)
                    downloaded_img = Image(filename=png2pdf_filename_full_path)
                    no_pad = True
                except wand.exceptions.PolicyError as exc:
                    logger.error(
                        f"id {story_as_object.id}: wand PolicyError for {story_as_object.thumb_filename_details['base_name']}"
                    )
                except Exception as exc:
                    logger.error(
                        f"id {story_as_object.id}: {story_as_object.thumb_filename_details['base_name']}, "
                        f"error with PDF: {exc}; "
                        f"traceback:\n{traceback.format_exc()}"
                    )
                    story_as_object.has_thumb = False
                    return

            # check for minimum size
            if (
                min(downloaded_img.width, downloaded_img.height)
                < config.settings["OG_IMAGE"]["MIN_DIM_PX"]
            ):
                story_as_object.has_thumb = False
                return

            # remove metadata
            downloaded_img.strip()

            # remove transparency, add border, crop and adjust aspect ratio,
            image_to_use = get_image_to_use(
                story_as_object,
                downloaded_img,
                force_aspect=force_aspect,
                no_trim=no_trim,
                no_pad=no_pad,
            )

            if not image_to_use:
                story_as_object.has_thumb = False
                return

            # standard resizing
            # with Image(image=image_to_use) as small_thumb:
            #     with small_thumb.convert("webp") as webp_image:
            #         webp_image.compression_quality = (
            #             WEBP_SMALL_THUMB_COMPRESSION_QUALITY
            #         )
            #         webp_image.transform(
            #             resize=f"{config.settings['THUMBS']['WIDTH_PX']['SMALL']}x"
            #         )
            #         try:
            #             save_thumb_where_it_should_go(
            #                 webp_image, story_as_object, "small"
            #             )
            #         except Exception as exc:
            #             story_as_object.has_thumb = False
            #             return

            with Image(image=image_to_use) as medium_thumb:
                with medium_thumb.convert("webp") as webp_image:
                    webp_image.compression_quality = (
                        WEBP_MEDIUM_THUMB_COMPRESSION_QUALITY
                    )
                    webp_image.transform(
                        resize=f"{config.settings['THUMBS']['WIDTH_PX']['MEDIUM']}x"
                    )
                    try:
                        save_thumb_where_it_should_go(
                            webp_image, story_as_object, "medium"
                        )
                    except Exception as exc:
                        story_as_object.has_thumb = False
                        return

            # with Image(image=image_to_use) as large_thumb:
            #     with large_thumb.convert("webp") as webp_image:
            #         webp_image.compression_quality = (
            #             WEBP_LARGE_THUMB_COMPRESSION_QUALITY
            #         )
            #         webp_image.transform(
            #             resize=f"{config.settings['THUMBS']['WIDTH_PX']['LARGE']}x"
            #         )
            #         try:
            #             save_thumb_where_it_should_go(
            #                 webp_image, story_as_object, "large"
            #             )
            #         except Exception as exc:
            #             story_as_object.has_thumb = False
            #             return

            with Image(image=image_to_use) as extralarge_thumb:
                with extralarge_thumb.convert("webp") as webp_image:
                    webp_image.compression_quality = (
                        WEBP_EXTRALARGE_THUMB_COMPRESSION_QUALITY
                    )
                    webp_image.transform(
                        resize=f"{config.settings['THUMBS']['WIDTH_PX']['EXTRALARGE']}x"
                    )
                    try:
                        save_thumb_where_it_should_go(
                            webp_image, story_as_object, "extralarge"
                        )
                    except Exception as exc:
                        story_as_object.has_thumb = False
                        return

            file_utils.delete_file(story_as_object.downloaded_orig_thumb_full_path)

            story_as_object.image_slug = create_img_slug_html(
                story_as_object, img_loading
            )

    except Exception as exc:
        logger.error(
            f"{sys._getframe(  ).f_code.co_name}: id {story_as_object.id}: {exc}"
        )
        if "Invalid URL" in str(exc):
            story_as_object.has_thumb = False
        elif "no decode delegate for this image format" in str(
            exc
        ):  # probably an html file
            story_as_object.has_thumb = False
        elif "Not a JPEG file: starts with 0x3c 0x21" in str(
            exc
        ):  # probably an html file
            story_as_object.has_thumb = False
        elif "Not a JPEG file" in str(exc):
            story_as_object.has_thumb = False
        elif "improper image header" in str(exc):
            story_as_object.has_thumb = False
        elif "orig_image's height or width is less than" in str(exc):
            story_as_object.has_thumb = False
        elif "nrecognized color" in str(exc):  # i.e., "[Uu]nrecognized color"
            story_as_object.has_thumb = False
        elif "OptionWarning: geometry does not contain image" in str(exc):
            story_as_object.has_thumb = False
        elif "must specify image size" in str(exc):
            story_as_object.has_thumb = False
        elif "corrupt image" in str(exc):
            story_as_object.has_thumb = False
        elif "xmlParseStartTag: invalid element name" in str(exc):
            story_as_object.has_thumb = False
        elif "insufficient image data in file" in str(exc):
            story_as_object.has_thumb = False
        elif "No scheme supplied." in str(exc):
            # TODO: this might be able to be fixed
            story_as_object.has_thumb = False
        elif "invalid colormap index" in str(exc):
            story_as_object.has_thumb = False
        elif "unable to open file `/tmp/magick" in str(exc):
            # in case this is a transient error, don't write placeholder
            pass
        logger.error(
            f"id {story_as_object.id}: story_as_object dump: {story_as_object}"
        )
        logger.error(
            f"id {story_as_object.id}: traceback: {print(traceback.format_exc())}"
        )

        return


def fix_multipage_pdf(story_as_object):
    try:
        with open(
            story_as_object.downloaded_orig_thumb_full_path, "rb"
        ) as pdf_file_stream:
            pdf_file = PdfReader(pdf_file_stream, strict=False)
            story_as_object.pdf_page_count = len(pdf_file.pages)
            if len(pdf_file.pages) > 1:
                outfile = PdfWriter()
                outfile.add_page(pdf_file.pages[0])
                temp_pdf_filename = f"temp-{story_as_object.id}.pdf"
                temp_pdf_full_path = os.path.join(
                    config.settings["TEMP_DIR"], temp_pdf_filename
                )
                with open(temp_pdf_full_path, "wb") as output_stream:
                    outfile.write(output_stream)
    except Exception as exc:
        logger.error(
            f"{sys._getframe(  ).f_code.co_name}: id {story_as_object.id}: error while discarding all but first page of PDF: {exc}"
        )
        raise exc

    shutil.copyfile(temp_pdf_full_path, story_as_object.downloaded_orig_thumb_full_path)
    logger.info(
        f"fix_multipage_pdf(): story_as_object.downloaded_orig_thumb_full_path: {story_as_object.downloaded_orig_thumb_full_path}"
    )
    story_as_object.thumb_aspect_hint = "PDF page"
    logger.info(
        f"id {story_as_object.id}: success while discarding all but first page of PDF"
    )
    return True


def rasterize_pdf_using_ghostscript(story_as_object):
    pdf_filename_full_path = story_as_object.downloaded_orig_thumb_full_path
    cur_unix_time = int(time.time())
    pdf2png_filename = f"pdf2png-{story_as_object.id}-{cur_unix_time}.png"
    pdf2png_filename_full_path = os.path.join(
        config.settings["TEMP_DIR"], pdf2png_filename
    )

    cmd = []
    cmd.append(
        f"{config.settings['DELEGATES']['PDF2PNG'][config.settings['cur_host']]}"
    )
    cmd.append("-dBATCH")
    cmd.append("-dNOPAUSE")
    cmd.append("-dQUIET")
    cmd.append("-sDEVICE=png16m")
    cmd.append("-r600")
    cmd.append(f"-sOutputFile={pdf2png_filename_full_path}")
    cmd.append(f"{pdf_filename_full_path}")

    logger.info(f"rasterize_pdf_using_ghostscript(): cmd={cmd}")

    p = subprocess.run(cmd, capture_output=True)

    logger.info(f"after subprocess: {p}")

    if p.returncode != 0:
        logger.error(f"subprocess had return code {p.returncode}")
    else:
        logger.info(f"subprocess returned successfully")

    # add page outline
    try:
        pdf2png = Image(filename=pdf2png_filename_full_path)
        border_hw = int(pdf2png.width / 350)
        pdf2png.border("white", 5 * border_hw, 5 * border_hw)
        # pdf2png.border('white', 4 * border_hw, 4 * border_hw)
        pdf2png = draw_dogear(pdf2png)
        pdf2png.save(filename=pdf2png_filename_full_path)
        return pdf2png_filename_full_path
    except Exception as e:
        logger.error(f"id {story_as_object.id}: failed to add page outline; error: {e}")
        # wand.exceptions.WandRuntimeError: MagickReadImage returns false, but did not raise ImageMagick  exception. This can occur when a delegate is missing, or returns EXIT_SUCCESS without generating a raster.
        return pdf_filename_full_path


def get_background_pixel(img):
    # sample pixels
    inset_distance = 10  # in pixels
    pixel_samples = []

    try:
        for xy in range(15):
            # pixel access is [yoffset][xoffset]
            # NW pixels
            pixel_samples.append(str(img[xy + inset_distance][xy + inset_distance]))
            # SE pixels
            pixel_samples.append(
                str(
                    img[img.height - xy - inset_distance][
                        img.width - xy - inset_distance
                    ]
                )
            )
            # SW pixels
            pixel_samples.append(
                str(img[img.height - xy - inset_distance][xy + inset_distance])
            )
            # NE pixels
            pixel_samples.append(
                str(img[xy + inset_distance][img.width - xy - inset_distance])
            )
    except Exception as e:
        logger.error(
            f"get_background_pixel(): error while sampling for background pixel: {e}"
        )

    most_common_pixels = collections.Counter(pixel_samples).most_common()
    for (
        each_pixel_KV
    ) in (
        most_common_pixels
    ):  # do it this tedious way in case I would want to, say, skip over the transparent pixels and get the next most common pixel color that was not transparent
        if "srgba" in each_pixel_KV[0]:
            background_pixel_as_Color = Color(
                config.settings["THUMBS"]["BG_COLOR_FOR_TRANSPARENT_THUMBS"]
            )
            break
        else:
            background_pixel_as_Color = Color(each_pixel_KV[0])
            break
    return background_pixel_as_Color


def get_cropped_image(img, crop_distance_in_px):
    cropped_image = Image(image=img)
    try:
        cropped_image.crop(
            left=crop_distance_in_px,
            top=crop_distance_in_px,
            width=cropped_image.width - 2 * crop_distance_in_px,
            height=cropped_image.height - 2 * crop_distance_in_px,
        )
    except Exception as e:
        logger.error(f"get_cropped_image(): error while cropping: {e}")
    return cropped_image


def get_bordered_img(img, background_pixel):
    bordered_img = Image(image=img)
    bordered_img.background_color = background_pixel
    border_percent = config.settings["WAND"]["BORDER_EXPANSION_PCT"] / 100
    bordered_img.border(
        background_pixel,
        height=int(bordered_img.height * border_percent),
        width=int(bordered_img.width * border_percent),
    )
    return bordered_img


def get_altered_img(img, aspect=None, force_aspect=None):
    if not aspect and not force_aspect:
        return None

    if force_aspect:
        aspect = force_aspect

    altered_img = Image(image=img)

    image_ratio_w2h = altered_img.width / altered_img.height

    if aspect == "square":
        if image_ratio_w2h == 1.0:
            # already square!
            pass
        elif image_ratio_w2h < 1.0:
            needed_width = altered_img.height
            x_offset = int((needed_width - altered_img.width) / -2)
            altered_img.extent(width=int(needed_width), x=x_offset)
        else:  # image_ratio_w2h > 1.0:
            needed_height = altered_img.width
            y_offset = int((needed_height - altered_img.height) / -2)
            altered_img.extent(height=int(needed_height), y=y_offset)
        return altered_img

    if aspect == "bar":
        if image_ratio_w2h == 3.0:
            # already a bar!
            pass
        elif image_ratio_w2h < 3.0:
            needed_width = altered_img.height * 3
            x_offset = int((needed_width - altered_img.width) / -2)
            altered_img.extent(width=int(needed_width), x=x_offset)
        else:  # image_ratio_w2h > 3.0:
            needed_height = altered_img.width / 3
            y_offset = int((needed_height - altered_img.height) / -2)
            altered_img.extent(height=int(needed_height), y=y_offset)
        return altered_img

    if aspect == "scratched":
        with Drawing() as draw:
            draw.fill_color = Color("red")
            draw.stroke_color = Color("red")
            draw.stroke_width = 50
            draw.line((0, 0), altered_img.size)
            draw(altered_img)
            return altered_img


def get_image_to_use(
    story_as_object,
    downloaded_img,
    force_aspect=None,
    no_trim=False,
    no_pad=False,
    shortcode="image",
):
    if downloaded_img.alpha_channel:
        downloaded_img.background = config.settings["THUMBS"][
            "BG_COLOR_FOR_TRANSPARENT_THUMBS"
        ]
        downloaded_img.merge_layers("flatten")
        logger.info(
            f"id {story_as_object.id}: og:image with transparency was flattened ; URL: {story_as_object.linked_url_og_image_url_final}"
        )

    cropped_img = get_cropped_image(downloaded_img, 4)

    trimmed_img = Image(image=cropped_img)

    background_pixel = get_background_pixel(trimmed_img)
    fuzz_factor = (
        config.settings["WAND"]["FUZZ_FACTOR_PCT"] * trimmed_img.quantum_range / 100
    )
    trimmed_img.trim(fuzz=fuzz_factor)

    # if trimmed_img is too small, don't use image at all
    if (
        min(trimmed_img.width, trimmed_img.height)
        < config.settings["OG_IMAGE"]["MIN_DIM_PX"]
    ):
        return None

    # check for ineffective trim
    if (
        trimmed_img.width / downloaded_img.width > 0.9
        and trimmed_img.height / downloaded_img.height > 0.9
    ):
        return downloaded_img

    # don't trim or pad original image if certain flags are set
    if no_trim:
        return downloaded_img

    # otherwise, proceed to add border, alter aspect ratio of canvas, etc.
    bordered_img = get_bordered_img(trimmed_img, background_pixel)

    image_ratio_w2h = bordered_img.width / bordered_img.height
    image_ratio_h2w = bordered_img.height / bordered_img.width

    # check for no_pad
    if no_pad:
        image_to_use = Image(image=bordered_img)

    # check if it's a PDF page
    elif story_as_object.thumb_aspect_hint == "PDF page":
        logger.info(
            f"id {story_as_object.id}: won't alter aspect ratio of PDF page-based thumb"
        )
        image_to_use = Image(image=bordered_img)

    # check if it's too tall to use
    elif image_ratio_h2w > 4:  # image_ratio_w2h < 0.25
        altered_img = get_altered_img(
            bordered_img, aspect="scratched", force_aspect=force_aspect
        )
        image_to_use = Image(image=altered_img)

    # pad tall image to square
    elif image_ratio_h2w > 1.15:  # image_ratio_w2h < 0.87
        altered_img = get_altered_img(
            bordered_img, aspect="square", force_aspect=force_aspect
        )
        image_to_use = Image(image=altered_img)

    # check if we can use it as is (squarish enough)
    elif 0.85 <= image_ratio_h2w <= 1.15:
        image_to_use = Image(image=bordered_img)

    # check if it's too wide to use
    elif image_ratio_w2h > 8:
        altered_img = get_altered_img(
            bordered_img, aspect="scratched", force_aspect=force_aspect
        )
        image_to_use = Image(image=altered_img)

    # pad wide image to bar
    else:  # image_ratio_w2h <= 8:
        altered_img = get_altered_img(
            bordered_img, aspect="bar", force_aspect=force_aspect
        )
        image_to_use = Image(image=altered_img)

    return image_to_use


def draw_dogear(pdf_page_img):
    logger.info(f"entering draw_dogear() with pdf_page_img {pdf_page_img}")

    # pdf_page_img = Image(filename="prepared-image-small.webp")
    width = pdf_page_img.width
    height = pdf_page_img.height

    outer_white_border_width_px = int(width / 350 * 4)  # 4
    width_of_dogear_px = int(width / 350 * 36)  # 36

    one_px = int(width / 350)
    two_px = int(width / 350 * 2)
    three_px = int(width / 350 * 3)

    # cut off corner
    with Drawing() as draw:
        draw.stroke_color = Color("white")
        draw.stroke_width = width / 350  # 1
        draw.fill_color = Color("white")
        for offset in range(outer_white_border_width_px + width_of_dogear_px + 1):
            draw.line(
                (width - width_of_dogear_px + offset, 0),
                (width, width_of_dogear_px - offset),
            )

        draw.stroke_color = Color("black")
        draw.stroke_line_cap = "butt"
        draw.stroke_line_join = "round"
        dogear_vertices = [
            (width - width_of_dogear_px + two_px, outer_white_border_width_px),  # north
            (
                width - outer_white_border_width_px - one_px,
                width_of_dogear_px - three_px,
            ),  # east
            (
                width - width_of_dogear_px + two_px,
                width_of_dogear_px - three_px,
            ),  # southwest
        ]
        draw.polygon(dogear_vertices)

        # draw.stroke_color = Color('black')
        draw.fill_opacity = 0.0
        page_vertices = [
            (
                width - width_of_dogear_px + two_px,
                outer_white_border_width_px,
            ),  # top, then right
            (outer_white_border_width_px, outer_white_border_width_px),  # top left
            (
                outer_white_border_width_px,
                height - outer_white_border_width_px,
            ),  # bottom left
            (
                width - outer_white_border_width_px - one_px,
                height - outer_white_border_width_px,
            ),  # bottom right
            (
                width - outer_white_border_width_px - one_px,
                width_of_dogear_px - three_px,
            ),  # right, then top
        ]
        draw.polygon(page_vertices)

        draw.draw(pdf_page_img)
        # pdf_page_img.save(filename="out2.png")

        logger.info(f"exiting draw_dogear() successfully")

        return pdf_page_img
