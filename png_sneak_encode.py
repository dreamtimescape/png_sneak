#!/usr/bin/env python3
# --------------------------------------------------------------------
# png_sneak_encode.py - Sneak a payload into a PNG image file
#                       without altering the pixel data.
#
# By timescape
# Started with code provided by RSAXVC - Thanks!
# https://github.com/dreamtimescape/png_sneak
# --------------------------------------------------------------------
"""
Sneak a payload into a PNG Image without altering pixel content

Usage:
python3 png_sneak_encode.py input_file output_file payload_file
or 
python3 png_sneak_encode.py input_file output_file "payload string"

This stegonagraphic tool encodes a payload into a PNG file.
The payload can be provided as a file or a string literal.
The payload is encoded into the row-filter portions of the PNG
file, leaving the actual image data untouched.

This can drastically change the actual bytes of the PNG file,
but will not alter the pixel data in any way. (hopefully)

As of this writing, the PNG spec uses only one Filter method (0)
which can use one of five possible filters for each row of the image.

Two bits of the payload can thus be placed into each row of the
image. Filters 0-3 are used for payload data, using their 2-bit
binary representation:

0 - 00
1 - 01
2 - 10
3 - 11

filter type 4 is used by the encoder for rows after the payload
content, and is ignored by the decoder.

The payload is possibly compressed by zlib if it will reduce
in size. If the payload is pure ASCII, an additional compression
attempt will be made by removing the '0' from the front of each byte
and only transmitting 7-bits per character.

This gives three possible payload compression methods, and the first
row's filter is used to encode which type was used:

compression - filter value
    none    -   0
    zlib    -   1
    7-bit   -   2
    
--------------------------------------------------------------------
"""

import argparse
import os.path
# Use png From package purepng
# documentation here:
# https://readthedocs.org/projects/purepng/downloads/pdf/stable/
import png
import zlib
from bitstring import BitStream

# Global variables
# I don't understand these. I feel like a script kiddie trying
# to make big. But the code appears to work when I do this.

# Global that keeps track of the current row
# Used to allow the first row to encode the compression type
# while the rest of the rows encode the payload
cur_row = 0

# Global that indicates the compression style for the payload
compress = 0

# Global used for the bits of the payload.
bits = BitStream()

# Global to indicate length of dashes '-' to output for print()
num_dashes = 45

def adapt_stego(line, cfg, filter_obj):
    """
    Return the line data for the given line, with the 
    desired 2-bit filter value.
    
    Normally, this would be an adapter filter trying to
    minimize PNG size. Instead, we override it by encoding
    2 bits from the data stream into each row.
    
    The encoding filter for the first row is the compression type:
        0   = none
        1   = zlib
        2   = 7-bit
        3-4 = undefined

    The encoding patterns for other rows are:
        0-3 = 2 bits of payload
        4   = unused / ignored by decoder
    """
    
    # Keeps track of which row we're on
    global cur_row
    
    # Stores the compression type
    global compress
    
    # Calculate all the possible filtered lines
    lines = filter_obj.filter_all(line)
    
    # Pick the line we need
    if cur_row == 0:
        # The first line encodes the compression type
        result = lines[compress]
    else:
        # Remaining lines encode the payload
        filter = stego()
        result = lines[filter]
        
    # Increment the row counter
    cur_row += 1
    return result

def getBytes(filename):
    """
    Return the bytes from a file
    """
    
    try:
        return open(filename, "rb").read()
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR reading File: %s\n%s" % (filename, e)
            )

def is_ascii(text):
    """
    Return true if text is pure ASCII
    """
    
    if isinstance(text, str):
        try:
            text.encode("ascii")
        except UnicodeEncodeError:
            return False
    else:
        try:
            text.decode("ascii")
        except UnicodeDecodeError:
            return False
    return True

def stego():
    """
    Return 2 bits at a time until out of bits, then return 4
    """
    
    # This seems to work with or without the global indicator for bits
    # I don't know why?
    global bits
    
    result = 4
    if (bits.len - bits._pos) > 1:
        result = bits.read("uint:2")
        
    return result

def main():
    """
    Import the input PNG file and the payload. Create the output PNG
    """
    
    # I don't understand global variables, but the code seems to work
    # when I do this.
    global bits
    global compress
    global cur_row
    
    # Define and Import the arguments
    # all are required
    parser = argparse.ArgumentParser()
    parser.add_argument("input", 
                        help = "input file path"
                        )
    parser.add_argument("output", 
                        help = "output file path"
                        )
    parser.add_argument("payload",
                        help = "payload file path or payload string"
                        )
    args = parser.parse_args()

    # Read in the input image, to get the needed info.
    # This will be used on the writer to (hopefully)
    # ensure the output PNG has the same pixel data
    # as the input PNG
    print("%s" % "-" * num_dashes)
    print("Input PNG: %s" % args.input)
    print("%s" % "-" * num_dashes)
    r = png.Reader(args.input)
    # Try to read it
    try:
        orig_png = r.read()
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR reading Input PNG File: %s\n%s" % (args.input, e)
            )

    # png.Reader() returns (width, height, pixels, metadata)
    # width and height are integers
    # pixels is the pixel data in "boxed row flat pixel format"
    # metadata is a dictionary
    meta = orig_png[3]

    # Assign to variables
    # Some of these values become properties of the Reader
    width = r.width
    height = r.height
    greyscale = r.greyscale
    alpha = r.alpha
    bitdepth = r.bitdepth

    # Some of these values are optional members of the metadata
    # Default values are assigned if the keys are not present
    # These default values are taken from the purepng documentation
    palette = meta.get("palette", None)
    palette_length = 0
    if palette is not None:
        palette_length = len( palette )
    transparent = meta.get("transparent", None)
    background = meta.get("background", None)
    gamma = meta.get("gamma", None)
    compression = meta.get("compression", None)
    interlace = meta.get("interlace", None)
    chunk_limit = meta.get("chunk_limit", 1048576)
    filter_type = meta.get("filter_type", None)
    icc_profile = meta.get("icc_profile", None)
    icc_profile_name = meta.get("icc_profile_name", "ICC Profile")

    # Print out some of the info
    print("Width:       %d" % width)
    print("Height:      %d" % height)
    print("Greyscale:   %s" % greyscale)
    print("Alpha:       %s" % alpha)
    print("Bitdepth:    %s" % bitdepth)
    print("Palette Len: %s" % palette_length)
    print()

    # Grab the pixel data
    orig_pixels = orig_png[2]

    # Convert the payload into bytes
    # Check if it's a file or a string
    if os.path.isfile(args.payload):
        raw_bytes = bytearray(getBytes(args.payload))
    else:
        raw_bytes = bytearray(args.payload, encoding="utf8")

    # Calculate the size of the raw payload
    raw_size = len(raw_bytes)
    print ("raw:   %s bytes" % raw_size)

    # Create the list of sizes for determining which one to use
    sizes = [raw_size]

    # Compress the raw payload using zlib
    # Remove the zlib header/tail using wbits = -15.
    # this option appears only available using the compressobj()
    # instead of the compress() function
    # Note this attempts to do it all in one chunk.
    # IMPROVEMENT: process in multiple chunks for large payloads
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    compressed_bytes = compressor.compress(raw_bytes)
    compressed_bytes += compressor.flush()

    # Calculate the size of the compressed payload
    zlib_size = len(compressed_bytes)
    print ("zlib:  %s bytes" % zlib_size)
    sizes.append(zlib_size)

    # Check if the input is pure-ASCII
    if is_ascii(raw_bytes):
        print ("Input is pure ASCII\nwill attempt 7-bit option")
        ascii_bits = BitStream(raw_bytes)
        # Remove the first bit from each byte
        # as it is '0' for ASCII characters
        del ascii_bits[::8]
        # calculate the length in bits
        ascii_len = len(ascii_bits)
        # We work with groups of 2 bits, so length must be even.
        # Pad with a trailing '0' if needed
        if ascii_len % 2 > 0:
            ascii_bits += BitStream("0b0")
        # Calculate the length in bytes
        ascii_size = len(ascii_bits) / 8
        print ("7-bit: %s bytes" % ascii_size)
        sizes.append(ascii_size)

        # Little diversion note...
        # I tried to be clever and beat zlib by compressing this 7-bit
        # per symbol version of pure ASCII input. Nope, didn't work!
        # zlib does a *much* better job of compressing ASCII text with
        # 8-bit characters than my 7-bit per character attempt.
        # Turns out zlib operates on bytes, so the 7-bit per character
        # input gets read as 8-bits per symbol, thus screwing up the
        # dictionary as more than 128 possible 8-bit characters can be
        # present.
        # oh well. Lesson learned.

    # Set payload compression style
    # 0 = none / raw
    # 1 = zlib
    # 2 = 7-bit

    # Find the smallest byte size of the options
    min_size_index = sizes.index(min(sizes))
    if min_size_index == 0:
        print("Using: Raw Option")
        compress = 0
        bits = BitStream(raw_bytes)
    elif min_size_index == 1:
        print("Using: zlib Option")
        compress = 1
        bits = BitStream(compressed_bytes)
    elif min_size_index == 2:
        print("Using: 7-bit Option")
        compress = 2
        # this is already a BitStream
        bits = ascii_bits

    # Add a blank line to the output
    print()

    # Need 2 extra bits for the compression style
    bits_to_encode = bits.len + 2
    print("bits to encode: %s" % str(bits_to_encode))

    # Each row can hold 2 bits
    required_rows = int(bits_to_encode / 2)
    print("rows needed:    %s" % required_rows)
    print("rows provided:  %s" % height)
    if(required_rows > height):
        print("%s" % "-" * num_dashes)
        raise SystemExit(
            "ERROR: Image too small. Need %s rows to encode paylod"
            % required_rows
            )

    # Set the custom filter_type for packing
    # the payload into the filter values
    png.register_extra_filter(adapt_stego, "stego")
    filter_type = "stego"

    # Write out the output file
    # Using the PNG parameters pulled from the input
    # file, except for the 'filter_type' which was changed
    # Try to open it
    try:
        f = open(args.output, "wb")
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR opening Output PNG File: %s\n%s" % (args.output, e)
            )

    # Create the writer with the Input PNG file's parameters
    # (except for the filter_type, which is the whole point)
    w = png.Writer( width, 
                    height, 
                    greyscale,
                    alpha,
                    bitdepth,
                    palette,
                    transparent,
                    background,
                    gamma,
                    compression,
                    interlace,
                    chunk_limit,
                    filter_type,
                    icc_profile,
                    icc_profile_name
                    )

    # Try to write it
    try:
        w.write(f, orig_pixels)
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR writing Output PNG File: %s\n%s" % (args.output, e)
            )
    finally:
        f.close()

    # Print results summary
    print("%s" % "-" * num_dashes)
    print("Payload Delivered!")
    print("%s" % "-" * num_dashes)
    print("Output PNG: %s" % args.output)

if __name__ == "__main__":
    main()
