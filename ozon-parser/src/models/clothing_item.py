class ClothingItem:
    def __init__(self, name, price, description, url, image_url):
        self.name = name
        self.price = price
        self.description = description
        self.url = url
        self.image_url = image_url

    def validate(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Invalid name for clothing item.")
        if not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValueError("Invalid price for clothing item.")
        if not isinstance(self.description, str):
            raise ValueError("Invalid description for clothing item.")
