# png_sneak
Python3 Encoder/Decoder for sneaking (small) content into/out of PNG files using the row filters, leaving the image pixel data unchanged

# Usage - encoder
    python3 png_sneak_encode.py input_file output_file payload_file

or

    python3 png_sneak_encode.py input_file output_file "payload string"

# Usage - decoder
    python3 png_sneak_decode.py input_file output_file

# Description
These stegonagraphic tools work with a payload hidden in a PNG file.
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

filter type 4 is used to indicate the end of the bitstream,
it and any filter types afterward are ignored by the decoder.

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
    
Since only 2 bits can be encoding into each row of the image,
this is a small-payload-friendly method.

Future improvements could include allowing multiple input files 
to be used, spreading the payload across the set.
Also, the code currently operates on the entire image data
in one chunk. This could likely use modification.
