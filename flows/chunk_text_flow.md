# chunk_text.py — flow

## split_by_headers(text)

```
split_by_headers(markdown_text)
    ↓
walk line by line
    ↓
line starts with "#"?
    ├── yes → save the PREVIOUS section (if one exists),
    │         start a new current_header + current_lines
    └── no  → append line to current_lines
    ↓
loop ends
    ↓
save the FINAL section (the one still in current_lines
when the file ends - the loop only saves on the NEXT
header, so the last section needs one extra save)
    ↓
return [(header_title, section_text), ...]
```

## chunk_section(text, chunk_size, overlap)

```
chunk_section(text, chunk_size=10, overlap=10)
    ↓
overlap >= chunk_size?
    ↓
ValueError (step would be 0 or negative -
the loop would never advance = infinite loop)

chunk_section(text, chunk_size=0, overlap=0)
    ↓
chunk_size <= 0?
    ↓
ValueError (nonsensical chunk size)

chunk_section("real text", chunk_size=20, overlap=5)
    ↓
valid inputs
    ↓
slide a window across the text, stepping forward by
(chunk_size - overlap) each time, so the last `overlap`
characters repeat in the next chunk
    ↓
return [chunk, chunk, chunk, ...]
```
