# SkinIdentifier

SkinIdentifier is a web application designed to help people find skincare products that better match their skin type. The platform supports customers, dermatologists, and administrators by making skincare recommendations more personalized and easier to understand.

## 1. Business Context

SkinIdentifier supports the skincare industry by helping people find products that match their skin type. It is used by customers, dermatologists, and administrators. The app makes it easier to choose the right skincare products and connect users with nearby stores.

## 2. Business Problem or Opportunity

Many people struggle to choose the right skincare products because they do not know their skin type and there are too many products to choose from. This often leads to wasted money and poor results. SkinIdentifier helps users make better skincare decisions with personalized recommendations.

## 3. Proposed Application

SkinIdentifier is a web application that uses AI to identify a user's skin type through a short questionnaire and an optional photo. It recommends products that match the user's skin type, allows users to save their profile, and shows which nearby stores have the recommended products in stock.

## 4. User Types

- Consumers: Find their skin type, receive personalized product recommendations, and save their skincare profile.
- Dermatologists: Review AI skin analyses and provide professional recommendations.
- Administrators: Manage products, update retailer information, and keep the system running correctly.

## 5. Business Objectives

- Help users choose the right skincare products and reduce incorrect purchases.
- Make skincare recommendations more personalized.
- Improve access to professional skincare guidance.
- Connect users with nearby retailers that have recommended products in stock.

## 6. Initial MVP Scope

The first version of SkinIdentifier will allow users to:

- Create an account
- Complete a skincare questionnaire
- Upload an optional skin photo
- Receive AI-generated skin type and product recommendations
- Save their skincare profile
- View nearby stores with available products

Administrator product management and dermatologist review features will also be included. More advanced features, such as chat with dermatologists, progress tracking, and additional AI tools, will be added in future versions.

## 7. Initial Data Needs

The application will store:

- Users
- Skincare profiles
- Questionnaire responses
- Skin analysis results
- Products
- Dermatologists
- Product recommendations
- Retail stores and inventory information
- Administrator data

## 8. Gemini AI Feature

Users will answer a skincare questionnaire and optionally upload a photo of their skin. Google Gemini will analyze this information to identify the user's skin type and generate personalized product recommendations with a short explanation of why each product is recommended. This helps users make better skincare decisions faster.

## 9. Similar Applications or Research

- Skin Bliss: Demonstrated how personalized product recommendations can improve the skincare shopping experience.
- Sephora Skin Scanner: Showed how AI skin analysis can help users better understand their skin and recommend suitable products.

## 10. Scope Concerns or Questions

- Ensuring the AI provides accurate recommendations for different skin types.
- Connecting to retailer inventory systems and keeping product availability up to date.
- Keeping the MVP realistic by focusing on the most important features first.

## Getting Started

### GitHub Codespaces

When the repository is opened in GitHub Codespaces, the development container will install the required Python dependencies automatically using the configuration in [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json).

### Run locally

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the development server:
   ```bash
   python manage.py runserver
   ```
4. Open http://127.0.0.1:8000/ in your browser.

The homepage displays the message: "Web Apps Project Template App".
