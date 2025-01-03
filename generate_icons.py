from PIL import Image, ImageDraw

def create_icon(size):
    # Create a new image with a white background
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    # Draw a blue circle
    margin = size // 10
    draw.ellipse(
        [(margin, margin), (size - margin, size - margin)],
        outline=(66, 133, 244),  # Google Blue
        fill=(66, 133, 244, 180),
        width=size // 20
    )

    # Draw clock hands
    center = size // 2
    # Hour hand
    draw.line(
        [(center, center), (center, center + size//4)],
        fill=(25, 25, 25),
        width=size // 15
    )
    # Minute hand
    draw.line(
        [(center, center), (center + size//3, center)],
        fill=(25, 25, 25),
        width=size // 15
    )

    return image

def main():
    # Create 48x48 icon
    icon48 = create_icon(48)
    icon48.save('icon48.png')

    # Create 128x128 icon
    icon128 = create_icon(128)
    icon128.save('icon128.png')

if __name__ == "__main__":
    main()
