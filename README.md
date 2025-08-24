# Fashion Assistant Web App

This is a web application called **Fashion Assistant** that helps users choose clothing based on photos and personal preferences.  

---

## Requirements

- Docker
- Docker Compose
- Modern web browser (to access the app at `http://localhost:5000`)

> No need to install Python or other dependencies locally, everything runs inside Docker.  

---

## How to Run

To build and start the application with all necessary dependencies, run:

```bash
docker-compose up --build 
```

----

## Notes

The database ozon_clothing_items.db and static files are mounted into the container, so any changes are preserved locally.

Secret keys and sensitive information should be stored in a .env file and not committed to the repository.