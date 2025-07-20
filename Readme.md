# Setup and Usage Guide

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed on your system.

---

## Challenge 1a

### Build the Docker Image

Open a terminal in the `Challenge_1a` directory and run:

```sh
docker build -t img1 .
```

### Run the Container

**On Windows (PowerShell):**

```powershell
docker run --rm `
  -v "${PWD}\sample_dataset\pdf:/sample_dataset/pdf" `
  -v "${PWD}\sample_dataset\outputs:/sample_dataset/outputs" `
  --network none img1
```

**On Linux/Mac:**

```sh
docker run --rm \
  -v "$(pwd)/sample_dataset/pdf:/sample_dataset/pdf" \
  -v "$(pwd)/sample_dataset/outputs:/sample_dataset/outputs" \
  --network none img1
```

---

## Challenge 1b

### Build the Docker Image

Open a terminal in the `Challenge_1b` directory and run:

```sh
docker build -t img2 .
```

### Run the Container

**On Windows (PowerShell):**

For **Collection 1**:

```powershell
docker run --rm `
  -v "${PWD}\Collection 1:/app/collections/Collection_1" `
  img2 python pdf_analyzer.py --collection "/app/collections/Collection_1"
```

For **Collection 2**:

```powershell
docker run --rm `
  -v "${PWD}\Collection 2:/app/collections/Collection_2" `
  img2 python pdf_analyzer.py --collection "/app/collections/Collection_2"
```

For **Collection 3**:

```powershell
docker run --rm `
  -v "${PWD}\Collection 3:/app/collections/Collection_3" `
  img2 python pdf_analyzer.py --collection "/app/collections/Collection_3"
```

**On Linux/Mac:**

```sh
docker run --rm \
  -v "$(pwd)/Collection 3:/app/collections/Collection_3" \
  img2 python pdf_analyzer.py --collection "/app/collections/Collection_3"
```

---

## Notes

- Make sure the required folders (`sample_dataset/pdf`, `sample_dataset/outputs`, `Collection 3`) exist in your project directory.
- Adjust paths as needed
