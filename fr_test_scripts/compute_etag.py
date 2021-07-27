import hashlib

files = ["partA", "partB", "partC"]
md5_digests = []
idx = 0

# Loop through all parts/files used for multipart
for file in files:
    with open(file, "rb") as f:
        # read byte contents
        contents  =  f.read()

        # get md5 on bytes
        file_md5 = hashlib.md5(contents)

        # get digest in hex for print
        file_hexdigest = file_md5.hexdigest()
        print("file's md5 is : {}".format(file_hexdigest))

        # Create byte digets for file and add to md5_digests list
        md5_digests.append(file_md5.digest())
        idx += 1

# Join individual byte digests and find finale digest
etag =  hashlib.md5(b''.join(md5_digests)).hexdigest() + '-' + str(len(md5_digests))
print("final etag is : {}".format(etag))
