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
from pypdf import PdfReader, PdfWriter
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
prepared_images_roster_by_exact_url = {
    "https://ar5iv.labs.arxiv.org/assets/ar5iv_card.png": "ar5iv-logo",
    "https://149521506.v2.pressablecdn.com/wp-content/uploads/2018/06/seth_godin_ogimages_v02_18061313.jpg": "seths-blog",
    "https://a0.awsstatic.com/libra-css/images/logos/aws_logo_smile_1200x630.png": "aws-logo-smile",
    "https://assets.msn.com/staticsb/statics/latest/homepage/msn-logo.svg": "msn-logo",
    "https://cdn.jamanetwork.com/images/logos/JAMA.png": "jama-network",
    "https://crystal-lang.org/assets/icon.png": "crystal-lang",
    "https://developer.mozilla.org/mdn-social-share.cd6c4a5a.png": "mdn-web-docs",
    "https://github.githubassets.com/assets/gist-og-image-54fd7dc0713e.png": "github-gist",
    "https://github.githubassets.com/images/modules/gists/gist-og-image.png": "github-gist",
    "https://global.discourse-cdn.com/swift/original/1X/0a90dde98a223f5841eeca49d89dc9f57592e8d6.png": "swift-lang-logo",
    "https://gwern.net/static/img/logo/logo-whitebg-large-border.png": "gwern-logo",
    "https://hacks.mozilla.org/files/2022/03/mdnplus.png": "hacks-mozilla",
    "https://lemire.me/img/portrait2018facebook.jpg": "lemire-portrait-2018-facebook",
    "https://lethain.com/static/author.png": "lethain-static-author",
    "https://s1.reutersmedia.net/resources_v2/images/rcom-default.png?w=800": "reuters",
    "https://savo.rocks/assets/img/favicons/favicon.png": "savo",
    "https://www.postgresql.org/media/img/about/press/elephant.png": "psql-press",
    "https://www.redditstatic.com/new-icon.png": "new-reddit-icon",
    "https://www.science.org/pb-assets/images/blogs/pipeline/default-image-1644619966880.png": "pipeline",
    "https://media.npr.org/include/images/facebook-default-wide.jpg": "npr-default",
    "https://static.npmjs.com/338e4905a2684ca96e08c7780fc68412.png": "npmjs",
    "https://static.arxiv.org/static/browse/0.3.4/images/arxiv-logo-fb.png": "arxiv-logo-fb",
    # "https://world.hey.com/dhh/avatar-20210222112907000000-293866624": "dhh",
    # "https://world.hey.com/dhh/avatar-df6405b0f7fafda980fd38b04c334bec936aef69": "dhh",
}


prepared_images_roster_by_url_prefix = {
    "https://world.hey.com/dhh/avatar-": "dhh",
    "https://149521506.v2.pressablecdn.com/wp-content/uploads/2018/06/seth_godin_ogimages_v02_": "seths-blog",
    "https://www.reuters.com/pf/resources/images/reuters/reuters-default.png": "reuters",
    "https://s1.reutersmedia.net/resources_v2/images/rcom-default.png": "reuters",
    "http://1.bp.blogspot.com/-vkF7AFJOwBk/VkQxeAGi1mI/AAAAAAAARYo/57denvsQ8zA/s1600-r/logo_chromium.png": "chromium-logo",
}

prepared_images_roster_by_url_suffix = {}

prepared_images_roster_by_url_substring = set()

domains_exempt_from_trim = [
    "opengraph.githubassets.com",
]

domains_with_higher_quality_resizing = [
    "opengraph.githubassets.com",
]

filename_substrings_making_exempt_from_trim = [
    "flag",
]

ignore_images_whose_urls_contain_these_substrings = [
    "https://www.redditstatic.com/new-icon.png",
]

ignore_images_at_these_urls = [
    "https://pastebin.com/i/facebook.png",
    "https://s0.wp.com/i/blank.jpg",
]

ignore_images_from_these_domains = set()

ignore_images_with_these_content_types = {
    "image/vnd.microsoft.icon",
    "image/avif",
    # "image/svg+xml",
}

ignore_images_with_these_filenames = {
    "blank.jpg",
    "logo-1200-630.jpg",
}


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
    for each_substring in prepared_images_roster_by_url_substring:
        if each_substring in og_image_url:
            return prepared_images_roster_by_url_substring[each_substring]
    return None


def get_webp_filename(story_as_object, size):
    return f"thumb-{story_as_object.id}-{size}.webp"


def get_webp_full_save_path(story_as_object, size):
    return os.path.join(
        config.settings["THUMBS_DIR"],
        get_webp_filename(story_as_object, size),
    )


def can_find_a_shortcode(story_as_object, img_loading):
    log_prefix = f"id {story_as_object.id}: "

    # logger.info(log_prefix+"checking for a shortcode...")
    # check if thumb is already available as prepared image
    prepared_image_shortcode = ""

    if (
        story_as_object.linked_url_og_image_url_final
        in prepared_images_roster_by_exact_url
        or story_as_object.linked_url_og_image_url_initial
        in prepared_images_roster_by_exact_url
    ):
        prepared_image_shortcode = prepared_images_roster_by_exact_url[
            story_as_object.linked_url_og_image_url_final
        ]

    if not prepared_image_shortcode:
        prepared_image_shortcode = shortcode_if_og_image_url_contains_certain_substring(
            story_as_object.linked_url_og_image_url_final
        )

    if prepared_image_shortcode:
        logger.info(
            log_prefix + f"using prepared image shortcode {prepared_image_shortcode}"
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
                    log_prefix + f"failed to upload thumb (prepared image) to S3: {exc}"
                )
                return False

            file_utils.delete_file(
                os.path.join(config.settings["TEMP_DIR"], thumb_filename)
            )

        story_as_object.image_slug = create_img_slug_html(story_as_object, img_loading)
        logger.info(
            log_prefix
            + f"using prepared image for image {story_as_object.linked_url_og_image_url_final}"
        )
        return True
    else:
        return False


def create_img_slug_html(story_as_object, img_loading="lazy"):
    return (
        '<div class="thumb">'
        f'<a href="{story_as_object.url}">'
        "<img "
        # "srcset="
        # f'"{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 4x, '
        # f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 3x, '
        # f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")} 2x, '
        # f'{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "medium")} 1x" '
        # 'sizes="(min-width: 1440px) 350px, (min-width: 1080px) 350px, (min-width: 768px) 350px, 350px" '
        f'src="{config.settings["THUMBS_URL"]}{get_webp_filename(story_as_object, "extralarge")}" '
        f'alt="{sanitize(story_as_object.title)}" '
        'class="thumb" '
        f'loading="{img_loading}" />'
        "</a>"
        "</div>"
    )


def save_thumb_where_it_should_go(webp_image, story_as_object, size):
    log_prefix = f"id {story_as_object.id}: save_thumb_where_it_should_go(): "
    thumb_filename = get_webp_filename(story_as_object, size)
    webp_image.save(filename=os.path.join(config.settings["TEMP_DIR"], thumb_filename))
    try:
        aws_utils.upload_thumb(thumb_filename=thumb_filename)
    except Exception as exc:
        logger.error(log_prefix + f"failed to upload thumb to S3: {str(exc)}")
        raise exc
    finally:
        file_utils.delete_file(
            os.path.join(config.settings["TEMP_DIR"], thumb_filename)
        )


def get_image_slug(story_as_object, img_loading="lazy"):
    log_prefix = f"id {story_as_object.id}: "
    log_prefix += "get_image_slug(): "
    story_as_object.image_slug = text_utils.EMPTY_STRING
    # bgcolor_as_Color = (None,)
    force_aspect = None
    no_trim = False
    no_pad = False

    # # check if we ignore this filename
    # if story_as_object.og_image_filename_details_from_url:
    #     if story_as_object.og_image_filename_details_from_url.filename:
    #         if (
    #             story_as_object.og_image_filename_details_from_url.filename
    #             in ignore_images_with_these_filenames
    #         ):
    #             logger.info(
    #                 log_prefix+f"ignore og:image based on filename {story_as_object.og_image_filename_details_from_url.filename}"
    #             )
    #             return

    # check if we ignore the exact URL
    if story_as_object.linked_url_og_image_url_final in ignore_images_at_these_urls:
        make_has_thumb_false(
            reason="ignore og:image based on exact URL",
            story_object=story_as_object,
            log_prefix=log_prefix,
            exc=None,
            log_tb=False,
        )
        return

    # check if we ignore this domain
    _, og_image_domains = url_utils.get_domains_from_url(
        story_as_object.linked_url_og_image_url_final
    )
    if og_image_domains in ignore_images_from_these_domains:
        make_has_thumb_false(
            reason="ignore og:image based on domain",
            story_object=story_as_object,
            log_prefix=log_prefix,
            exc=None,
            log_tb=False,
        )
        return

    # check if we ignore URLs starting with specific prefixes
    for x in prepared_images_roster_by_url_prefix.keys():
        if story_as_object.linked_url_og_image_url_final.startswith(x):
            make_has_thumb_false(
                reason="ignore og:image based on URL prefix",
                story_object=story_as_object,
                log_prefix=log_prefix,
                exc=None,
                log_tb=False,
            )
            return

    # check if we ignore URLs ending with specific suffixes
    for x in prepared_images_roster_by_url_suffix.keys():
        if story_as_object.linked_url_og_image_url_final.endswith(x):
            make_has_thumb_false(
                reason="ignore og:image based on URL suffix",
                story_object=story_as_object,
                log_prefix=log_prefix,
                exc=None,
                log_tb=False,
            )
            return

    # check for shortcode
    if can_find_a_shortcode(story_as_object, img_loading):
        story_as_object.has_thumb = True
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

    if magic_result in ignore_images_with_these_content_types:
        make_has_thumb_false(
            reason=f"ignore og:image based on content type {magic_result}",
            story_object=story_as_object,
            log_prefix=log_prefix,
            exc=None,
            log_tb=True,
        )
        return

    if (
        "image" in magic_result
        and "base_name" in story_as_object.og_image_filename_details_from_url
    ):
        for pattern in filename_substrings_making_exempt_from_trim:
            if (
                pattern
                in story_as_object.og_image_filename_details_from_url[
                    "base_name"
                ].lower()
            ):
                logger.info(
                    log_prefix
                    + f"will not trim image with base filename {story_as_object.og_image_filename_details_from_url['base_name']}"
                )
                force_no_trim = True
                no_trim = True
                break

        for pattern in ignore_images_whose_urls_contain_these_substrings:
            if (
                pattern
                in story_as_object.og_image_filename_details_from_url[
                    "base_name"
                ].lower()
            ):
                make_has_thumb_false(
                    reason=f"ignore image {story_as_object.og_image_filename_details_from_url['base_name']} based on substring {pattern}",
                    story_object=story_as_object,
                    log_prefix=log_prefix,
                    exc=None,
                    log_tb=True,
                )
                return

    # initialize webp compression levels from settings
    WEBP_SMALL_THUMB_COMPRESSION_QUALITY = int(
        config.settings["THUMBS"]["COMP_QUAL"]["SMALL"]
    )  # default value
    # WEBP_MEDIUM_THUMB_COMPRESSION_QUALITY = int(
    #     config.settings["THUMBS"]["COMP_QUAL"]["MEDIUM"]
    # )  # default value
    # WEBP_LARGE_THUMB_COMPRESSION_QUALITY = int(
    #     config.settings["THUMBS"]["COMP_QUAL"]["LARGE"]
    # )  # default value
    WEBP_EXTRALARGE_THUMB_COMPRESSION_QUALITY = int(
        config.settings["THUMBS"]["COMP_QUAL"]["EXTRALARGE"]
    )  # default value

    # preferentially render thumbs from certain domains with better quality
    if og_image_domains in domains_with_higher_quality_resizing:
        WEBP_SMALL_THUMB_COMPRESSION_QUALITY = min(
            100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 5
        )
        # WEBP_MEDIUM_THUMB_COMPRESSION_QUALITY = min(
        #     100, WEBP_SMALL_THUMB_COMPRESSION_QUALITY + 10
        # )
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
            no_pad = True
        except Exception as exc:
            make_has_thumb_false(
                reason="could not extract single page from PDF",
                story_object=story_as_object,
                log_prefix=log_prefix,
                exc=exc,
                log_tb=True,
            )
            return

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
                try:
                    if len(downloaded_img.sequence) > 1:
                        first_frame = downloaded_img.sequence[0]
                        logger.info(
                            log_prefix + f"{sys._getframe(  ).f_code.co_name}: "
                            f"used first frame of animation in {story_as_object.normalized_og_image_filename}"
                        )
                        downloaded_img = Image(image=first_frame)
                except Exception as exc:
                    make_has_thumb_false(
                        reason="failed to get first frame of animation",
                        story_object=story_as_object,
                        log_prefix=log_prefix,
                        exc=exc,
                        log_tb=True,
                    )
                    return

            # if SVG format, rasterize using Wand
            elif image_format in ["SVG"]:
                try:
                    vec_img = Image(
                        filename=story_as_object.downloaded_orig_thumb_full_path,
                        resolution=600.0,  # 1000.0 might have caused error
                    )
                except Exception as exc:
                    make_has_thumb_false(
                        reason=f"problem converting svg file {story_as_object.downloaded_orig_thumb_full_path}",
                        story_object=story_as_object,
                        log_prefix=log_prefix,
                        exc=exc,
                        log_tb=True,
                    )
                    return

                vec_img.background_color = Color("white")
                vec_img.alpha_channel = "off"
                vec_img.convert("png")
                vec_img.transform(resize="3000x")
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
                    make_has_thumb_false(
                        reason=f"wand PolicyError for {story_as_object.og_image_filename_details_from_url['base_name']}",
                        story_object=story_as_object,
                        log_prefix=log_prefix,
                        exc=exc,
                        log_tb=True,
                    )
                    return
                except Exception as exc:
                    make_has_thumb_false(
                        reason=f"error with PDF {story_as_object.og_image_filename_details_from_url['base_name']}",
                        story_object=story_as_object,
                        log_prefix=log_prefix,
                        exc=exc,
                        log_tb=True,
                    )
                    return

            # check for minimum size
            if (
                min(downloaded_img.width, downloaded_img.height)
                < config.settings["OG_IMAGE"]["MIN_DIM_PX"]
            ):
                make_has_thumb_false(
                    reason=f"image too small: {story_as_object.og_image_filename_details_from_url['base_name']}",
                    story_object=story_as_object,
                    log_prefix=log_prefix,
                    exc=None,
                    log_tb=False,
                )
                return

            # remove metadata
            try:
                downloaded_img.strip()
            except Exception as exc:
                make_has_thumb_false(
                    reason="error while stripping metadata from image",
                    story_object=story_as_object,
                    log_prefix=log_prefix,
                    exc=None,
                    log_tb=False,
                )
                return

            # remove transparency, add border, crop and adjust aspect ratio,
            image_to_use = None
            try:
                image_to_use = get_image_to_use(
                    story_as_object,
                    downloaded_img,
                    force_aspect=force_aspect,
                    no_trim=no_trim,
                    no_pad=no_pad,
                )
            except Exception as exc:
                make_has_thumb_false(
                    reason="problem in get_image_to_use()",
                    story_object=story_as_object,
                    log_prefix=log_prefix,
                    exc=None,
                    log_tb=True,
                )

                return

            if not image_to_use:
                return

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
                        return

            file_utils.delete_file(story_as_object.downloaded_orig_thumb_full_path)

            story_as_object.image_slug = create_img_slug_html(
                story_as_object, img_loading
            )
            if story_as_object.image_slug:
                story_as_object.has_thumb = True

    except Exception as exc:
        exc_name = str(exc.__class__.__name__)
        msg = str(exc)

        logger.error(log_prefix + f"{exc_name} {msg}")
        if "Invalid URL" in msg:
            pass
        elif "no decode delegate for this image format" in msg:  # probably an html file
            logger.error(
                log_prefix + f"no decode delegate for image type {image_format}"
            )
            pass
        elif "Not a JPEG file: starts with 0x3c 0x21" in msg:  # probably an html file
            pass
        elif "Not a JPEG file" in msg:
            pass
        elif "improper image header" in msg:
            pass
        elif "orig_image's height or width is less than" in msg:
            pass
        elif "nrecognized color" in msg:  # i.e., "[Uu]nrecognized color"
            pass
        elif "OptionWarning: geometry does not contain image" in msg:
            pass
        elif "must specify image size" in msg:
            pass
        elif "corrupt image" in msg:
            pass
        elif "xmlParseStartTag: invalid element name" in msg:
            pass
        elif "insufficient image data in file" in msg:
            pass
        elif "No scheme supplied." in msg:
            pass
        elif "invalid colormap index" in msg:
            pass
        elif "unable to open file `/tmp/magick" in msg:
            pass
        logger.error(log_prefix + f"story_as_object dump: {story_as_object}")
        tb_str = traceback.format_exc()
        logger.error(log_prefix + tb_str)


def make_has_thumb_false(
    reason=None, story_object=None, log_prefix="", exc=None, log_tb=False
):
    if not reason:
        raise Exception("must supply reason for no thumb")
    if exc:
        exc_name = exc.__class__.__name__
        exc_msg = str(exc)
        exc_slug = f"{exc_name} {exc_msg}"
    else:
        exc_slug = ""
        log_tb = False

    log_prefix += "make_has_thumb_false(): "

    story_object.has_thumb = False
    story_object.reason_for_no_thumb = f"{reason}: {exc_slug}"
    logger.info(log_prefix + story_object.reason_for_no_thumb)
    if log_tb:
        tb_str = traceback.format_exc(exception=exc)
        logger.info(log_prefix + tb_str)


def fix_multipage_pdf(story_as_object):
    log_prefix = f"id {story_as_object.id}: "
    log_prefix += "fix_multipage_pdf(): "
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
            log_prefix + f"error while discarding all but first page of PDF: {str(exc)}"
        )
        raise exc

    shutil.copyfile(temp_pdf_full_path, story_as_object.downloaded_orig_thumb_full_path)
    logger.info(
        log_prefix
        + f"story_as_object.downloaded_orig_thumb_full_path: {story_as_object.downloaded_orig_thumb_full_path}"
    )
    story_as_object.thumb_aspect_hint = "PDF page"
    logger.info(log_prefix + "success discarding all but first page of PDF")
    return True


def rasterize_pdf_using_ghostscript(story_as_object):
    log_prefix = f"id {story_as_object.id}: "
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

    # logger.info(log_prefix + f"rasterize_pdf_using_ghostscript(): cmd={cmd}")

    p = subprocess.run(cmd, capture_output=True)

    # logger.info(log_prefix + f"after subprocess: {p}")

    if p.returncode != 0:
        logger.error(
            log_prefix
            + f"subprocess had non-zero return code {p.returncode} ; cmd={cmd}"
        )
    # else:
    #     logger.info(log_prefix + "subprocess returned successfully")

    # add page outline and dogear
    try:
        pdf2png = Image(filename=pdf2png_filename_full_path)
        border_hw = int(pdf2png.width / 350)
        pdf2png.border("white", 5 * border_hw, 5 * border_hw)
        # pdf2png.border('white', 4 * border_hw, 4 * border_hw)
        pdf2png = draw_dogear(pdf2png, log_prefix=log_prefix)
        pdf2png.save(filename=pdf2png_filename_full_path)
        return pdf2png_filename_full_path
    except Exception as exc:
        logger.error(
            log_prefix + f"failed to add page outline and dogear; error: {str(exc)}"
        )
        # wand.exceptions.WandRuntimeError: MagickReadImage returns false, but did not raise ImageMagick exception. This can occur when a delegate is missing, or returns EXIT_SUCCESS without generating a raster.
        return pdf_filename_full_path


def get_background_pixel(img, log_prefix=""):
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
    except Exception as exc:
        logger.error(
            log_prefix
            + f"get_background_pixel(): error while sampling for background pixel: {exc}"
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
    log_prefix = f"id {story_as_object.id}: "

    if downloaded_img.alpha_channel:
        downloaded_img.background = config.settings["THUMBS"][
            "BG_COLOR_FOR_TRANSPARENT_THUMBS"
        ]
        downloaded_img.merge_layers("flatten")
        logger.info(
            log_prefix
            + f"flattened transparency for og:image {story_as_object.linked_url_og_image_url_final}"
        )

    cropped_img = get_cropped_image(downloaded_img, 4)

    trimmed_img = Image(image=cropped_img)

    background_pixel = get_background_pixel(trimmed_img, log_prefix=log_prefix)
    fuzz_factor = (
        config.settings["WAND"]["FUZZ_FACTOR_PCT"] * trimmed_img.quantum_range / 100
    )
    trimmed_img.trim(fuzz=fuzz_factor)

    # if trimmed_img is too small, don't use image at all
    if (
        min(trimmed_img.width, trimmed_img.height)
        < config.settings["OG_IMAGE"]["MIN_DIM_PX"]
    ):
        logger.info(log_prefix + "trimmed image too small")
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
        logger.info(log_prefix + "won't alter aspect ratio of PDF page-based thumb")
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

    logger.info(log_prefix + "successfully trimmed og:image")
    return image_to_use


def draw_dogear(pdf_page_img, log_prefix=""):
    # logger.info(log_prefix + "entering draw_dogear()")

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

        logger.info(log_prefix + "successfully added a dogear")

        return pdf_page_img
