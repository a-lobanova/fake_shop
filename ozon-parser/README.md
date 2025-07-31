# Ozon Parser

This project is designed to scrape women's clothing items from the Ozon website and save them to a database. 

## Project Structure

```
ozon-parser
├── src
│   ├── parser.py          # Main entry point for the parser
│   ├── db.py              # Handles database connections and operations
│   ├── models
│   │   └── clothing_item.py # Defines the ClothingItem class
│   └── utils
│       └── ozon_scraper.py  # Utility functions for scraping Ozon
├── requirements.txt        # Lists project dependencies
└── README.md               # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd ozon-parser
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the parser, execute the following command:
```
python src/parser.py
```

This will initiate the scraping process and save the clothing items to the database.

## Dependencies

This project requires the following Python packages:
- requests
- BeautifulSoup4
- (any additional database libraries)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.