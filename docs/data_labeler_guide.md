# Data Labeler Guide

## Your role

You explain what the data means; you do not need to write code, RDF, or SPARQL. The system converts your choices into an ontology and knowledge graph. A labeler can upload files, describe them, check the result, and save the work. An administrator reviews and publishes it.

## Before you start

Prepare each source as a UTF-8 CSV file:

- Use the first row for clear column headings.
- Put one item or one connection on each row.
- Give every item a stable, unique ID.
- Reuse exactly the same ID when the item appears in another file.
- Remove blank rows and obvious duplicates.
- Do not include passwords, secrets, or unnecessary personal information.

It is easiest to use separate files for different types of things. Build the lists of things first and add connection files afterwards.

## The five-step workflow

### 1. Add data

Open **Modeling → 1. Add data** and choose a CSV file. Check that characters display correctly, headings are separate, values are in the right columns, and the counts look reasonable. Uploading does not publish anything.

### 2. Say what one row represents

Open **2. Describe data**. Choose **A list of things** for customers, products, orders, employees, or places. Give the type a singular name such as `Customer`.

Choose **Connections between things** when each row links two known IDs. Give the connection a short verb phrase such as `works for`.

### 3. Describe the columns

For a list of things:

| Meaning | Use it for |
|---|---|
| Unique ID | A stable value that distinguishes one item |
| Display name | The name people should see |
| Detail | A useful fact such as country, date, or category |
| Do not import | A technical, sensitive, or irrelevant column |

For a connection file:

| Meaning | Use it for |
|---|---|
| From item | The ID where the connection starts |
| To item | The ID where the connection ends |
| Connection name | Optional column containing the relationship name |
| Do not import | A column that should not be loaded |

### 4. Check and save

Resolve every **choice left** message, then select **Check and save**. Saving does not publish the file.

Do not guess. Ask the data owner when a column is ambiguous, codes are undocumented, IDs disagree, or personal information is present.

### 5. Review and publish

Use **3. Review ontology** to inspect published types, details, and connections. An administrator chooses **Add this file** for later files in the same model, or **Start a new graph** only for the first file of a completely new model.

## Worked examples

An item file:

```csv
customer_id,company_name,country
C001,Northwind Traders,UK
C002,Alpine Goods,Germany
```

Map `customer_id` to **Unique ID**, `company_name` to **Display name**, and `country` to **Detail**. Name one row `Customer`.

A connection file:

```csv
customer_id,order_id,relationship
C001,O1042,placed
C002,O1043,placed
```

Map `customer_id` to **From item**, `order_id` to **To item**, and `relationship` to **Connection name**. IDs must exactly match the item files.

## Final quality checklist

- Every item file has one Unique ID and one Display name.
- Every connection file has a From item and To item.
- IDs are stable and consistent across files.
- Names are understandable and consistently spelled.
- Sensitive and irrelevant columns are excluded.
- No meaning was invented or guessed.
- The preview and counts were checked.
- Every mapping says **Ready** before administrator review.

## Getting help

Record the file name, column name, a safe sample value, and your question. Do not copy confidential rows into chat or logs. Send the issue to the data owner or ontology administrator.
