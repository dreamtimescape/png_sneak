#!/usr/bin/env python3
# --------------------------------------------------------------------
# png_sneak_decode.py - Extract a Sneaky payload from a PNG image file
#
# By timescape
# https://github.com/dreamtimescape/png_sneak
# --------------------------------------------------------------------
"""
Extract Sneaky Payload from PNG Image's row filter information

Usage:
python3 png_sneak_decode.py input_filename output_filename

This stegonagraphic tool extracts a payload from a PNG file.
It is assumed that the payload was encoded into the file using the
corresponding encoder, which places the content into the row-filter 
portions of the PNG file, leaving the actual image data untouched.

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
# Use png From package purepng
import png
import zlib
from bitstring import BitStream

# Global variables
# I don't understand these. I feel like a script kiddie trying
# to make big. But the code appears to work when I do this.

# Global to indicate length of dashes '-' to output for print()
num_dashes = 45

def to_bytes( bits, size=8, pad='0'):
    """
    Return a bytearray from a bitstream, padding as needed
    """
    chunks = [bits[n:n+size] for n in range(0, len(bits), size)]
    if pad:
        chunks[-1] = chunks[-1].ljust(size, pad)
    return bytearray([int(c, 2) for c in chunks])

def main():
    """
    Extract the payload from a PNG file.
    """
    
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help = "input file path")
    parser.add_argument("output", help = "output file path")
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

    # Calculate bits_per_pixel
    # From: https://www.w3.org/TR/REC-png-961001#Chunks
    #   Color    Allowed    Interpretation
    #   Type    Bit Depths
    #   
    #   0       1,2,4,8,16  Each pixel is a grayscale sample.
    #   
    #   2       8,16        Each pixel is an R,G,B triple.
    #   
    #   3       1,2,4,8     Each pixel is a palette index;
    #                       a PLTE chunk must appear.
    #   
    #   4       8,16        Each pixel is a grayscale sample,
    #                       followed by an alpha sample.
    #   
    #   6       8,16        Each pixel is an R,G,B triple,
    #                       followed by an alpha sample.
    
    # Initialize
    bits_per_pixel = 0
    
    # Determine from metadata
    if palette:
        # If there's a palette, it's type 3
        color_type = 3
        # and each pixel only takes one sample
        bits_per_pixel = bitdepth
    elif greyscale:
        if alpha:
            # Greyscale + Alpha = type 4
            color_type = 4
            # each pixel takes two samples
            bits_per_pixel = bitdepth * 2
        else:
            # Greyscale = type 0
            color_type = 0
            # each pixel takes one sample
            bits_per_pixel = bitdepth
    else:
        if alpha:
            # RGB + Alpha = type 6
            color_type = 6
            # each pixel takes four samples
            bits_per_pixel = bitdepth * 4
        else:
            # RGB = type 2
            color_type = 2
            # each pixel takes 3 samples
            bits_per_pixel = bitdepth * 3

    # If nothing was found, it's an error
    if bits_per_pixel == 0:
        raise SystemExit(
            "ERROR: Unable to Calculate Bits Per Pixel"
            )
    
    # Display it:
    print("Bits Per Pixel: " + str(bits_per_pixel))

    # Pull out the decompressed IDAT (pixel) data
    data = list(r.idatdecomp())
    
    # Create bitstream
    bits = BitStream()
    
    # Combine all chunks of data
    # Note this attempts to do it all in one chunk
    # IMPROVEMENT: process in multiple chunks for large files
    for x in range(len(data)):
        bits += BitStream( data[x] )
    
    # Each line has a one-byte header containing the filter type
    # followed by [width] pixels, each of [bits_per_pixel] bits
    bits_per_line = 8 + width * bits_per_pixel
    
    # Lines have to begin on byte boundaries
    # So pad if necessary
    if bits_per_line % 8 > 0:
        bits_per_line += 8 - bits_per_line % 8

    # Initialize output bits string
    out_bits = str()
    
    # Loop through each row of the image
    for y in range(height):
        # Determine the starting position of the line
        start =  y * bits_per_line
        # Take eight bits for the row filter byte
        stop = start + 8
        
        # Pull out the row filter value in hex (base = 16)
        row_filter = int(str(bits[start:stop]), 16)
        # print ("Row: %d Filter:  %d" % (y, row_filter))
        
        # First row's filter indicates compression type
        # 0   = none
        # 1   = zlib
        # 2   = 7-bit
        # 3-4 = undefined
        if y == 0:
            # Determine compression type
            if 0 <= row_filter <= 2:
                compress = row_filter
                compression_types = ["none", 
                                    "zlib", 
                                    "7-bit", 
                                    "undefined", 
                                    "undefined"
                                    ]
                print("Payload compression type: %s"
                    % compression_types[compress]
                    )
            else:
                raise SystemExit(
                    "ERROR: Undefined payload compression method:\n"
                    + "First Row Filter = %s" % compress
                    )
                    
        # Convert the row filters for the remaining lines into bits
        # 0 = 00
        # 1 = 01
        # 2 = 10
        # 3 = 11
        # 4 = ignore
        else:
            if row_filter != 4:
                out_bits += str('{0:02b}'.format(row_filter))
    
    # Print the compressed payload info
    if compress:
        print("Compressed Payload Length: %d bytes" 
            % (len(out_bits) / 8)
            )

    # If 7-bit, add back in the first bit (0)
    if compress == 2:
        # Remove any trailing pad bit if length is not a multiple of 7
        if len(out_bits) % 7 > 0:
            out_bits = out_bits[:-1]
        # Insert a '0' before every 7-bits
        n = 7
        out_bits = '0' + '0'.join(
                                out_bits[s:s+n] 
                                for s in range(0, len(out_bits), n)
                                )
    
    # make it a bytearray
    out_bytes = to_bytes(out_bits)

    # decompress if needed
    if compress == 1:
    
        try:
            # Attempt to decompress the payload
            raw_bytes = zlib.decompress(out_bytes, -15)
        except Exception as e:
            # Something broke
            print("%s" % "-" * num_dashes)
            raise SystemExit(
            "ERROR Unable to decompress payload.\n%s" % (e)
            )
    else:
        raw_bytes = out_bytes

    # Display the info
    print("Payload Length: %s bytes" % len(raw_bytes))
    
    # Try to open the output file
    try:
        f = open(args.output, "wb")
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR opening Output File: %s\n%s" % (args.output, e)
            )

    # Try to write output file
    try:
        f.write(raw_bytes)
    # Exit with Error info it if didn't work
    except Exception as e:
        raise SystemExit(
            "ERROR writing Output PNG File: %s\n%s" % (args.output, e)
            )
    finally:
        f.close()

    # Display Summary
    print()
    print("Payload Delivered to:\n%s" % args.output)
    print("%s" % "-" * num_dashes)
    print("Payload:")
    print("%s" % "-" * num_dashes)
    # Try to display the payload
    try:
        # Output the payload contents if unicode text
        print("%s" % bytes(raw_bytes).decode())
    except UnicodeDecodeError:
        # Output an indicator of non-unicode text if not
        print("(non-unicode data. may appear strange)")
        print("%s" % "-" * num_dashes)
        print("%s" % repr(bytes(raw_bytes)))
    
if __name__ == "__main__":
    main()
