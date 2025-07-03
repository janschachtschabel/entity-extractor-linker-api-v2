# Entity Extractor & Linker API

[![CI/CD Pipeline](https://github.com/janschachtschabel/entity-extractor-linker-api/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/janschachtschabel/entity-extractor-linker-api/actions)
[![Code Quality](https://img.shields.io/badge/code%20quality-A+-green.svg)](https://github.com/janschachtschabel/entity-extractor-linker-api)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Eine hochperformante **FastAPI-basierte REST-API** zur intelligenten Extraktion, Verknüpfung und Analyse von Named Entities in beliebigen Texten. Die API nutzt moderne LLM-Technologie (OpenAI kompatibel) kombiniert mit Wikipedia für umfassende Textanalyse und Content-Generierung.

## 🎯 Kernfunktionen

### 📊 Entity Processing
- **Extraktion**: Automatische Erkennung von Personen, Orten, Organisationen, Ereignissen und Konzepten
- **Linking**: Verknüpfung mit Wikipedia für strukturierte Metadaten
- **Kategorisierung**: Intelligente Klassifizierung nach Entity-Typen
- **Mehrsprachigkeit**: Unterstützung für Deutsch und Englisch
- **Education Mode**: Multi-perspektivische Analyse von Themen aus verschiedenen Gesichtspunkten

### 📚 Kompendium-Generierung
- **Automatische Texterstellung**: Zusammenfassende Texte mit Wikipedia-Referenzen
- **Education Mode**: Multi-perspektivische Betrachtung von Themen aus verschiedenen Blickwinkeln
- **Strukturierte Ausgabe**: Formatierte Texte mit oder ohne Quellenangaben
- **Anpassbare Länge**: Konfigurierbare Textumfänge je nach Anforderung

### 🎓 QA-Paar-Generierung
- **Intelligente Fragenerstellung**: Automatische Generierung relevanter Fragen zu Textinhalten
- **Kontextbasierte Antworten**: Präzise Antworten basierend auf extrahierten Entities
- **Normierung von QA-Paaren**: Können nach auf verschiedene Werte normiert werden wie z.B. Bildungsstufen oder Lernzielniveaus (Bloomsche Taxonomie)

## 🚀 API-Endpoints

```
# Entity Processing
POST /api/linker           # Entity-Extraktion und Wikipedia-Linking

# Content Generation
POST /api/compendium       # Kompendium-Erstellung
POST /api/qa               # QA-Paar-Generierung

# Pipeline Processing
POST /api/pipeline         # Vollständige Verarbeitungs-Pipeline

# Utilities
GET  /api/utils           # Hilfsfunktionen und Tools

# System
GET  /health              # Service-Status
GET  /docs                # Interactive API-Dokumentation (Swagger UI)
GET  /redoc               # Alternative API-Dokumentation (ReDoc)
```

## ⚡ Performance & Skalierung

- **Asynchrone Verarbeitung**: Concurrent API-Calls für optimale Performance
- **Rate Limiting**: Schutz vor API-Überlastung
- **Batch Processing**: Effiziente Verarbeitung großer Textmengen
- **Strukturiertes Logging**: Umfassendes Monitoring mit Loguru

## � Quick Start

### Prerequisites

- **Python 3.13+** (recommended)
- **OpenAI API Key** for LLM functionality
- **Docker** (optional, for containerized deployment)

### Installation

```bash
# Clone repository
git clone https://github.com/janschachtschabel/entity-extractor-linker-api.git
cd entity-extractor-linker-api

# Install with development dependencies
pip install -e ".[dev]"

# Set up environment variables
export OPENAI_API_KEY="your-openai-api-key"

# Run the application
uvicorn app.main:app --reload
```

### Docker Deployment

```bash
# Build and run
docker build -t entityextractorbatch .
docker run -p 8000:8000 -e OPENAI_API_KEY="your-key" entityextractorbatch

# Health check
curl http://localhost:8000/health
```

## 🧪 Live Demo

**🚀 Try it now in Google Colab** (no installation required):

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1jKr9i6e2oA3TS-KwxFKrEEnUQo2Wxltd#scrollTo=hNDE-36iJmju)

Das Notebook enthält:
- Vollständige API-Installation in Google Colab
- Cloudflare Tunnel für öffentlichen Zugriff

## 📈 Performance

### Pipeline Benchmarks

- **Entity Extraction**: ~5-15 seconds (depending on text complexity)
- **Wikipedia Linking**: ~2-8 seconds (with intelligent fallbacks)
- **Content Generation**: ~20-40 seconds (for 5000+ word content)
- **Q&A Generation**: ~3-8 seconds (for 10+ question pairs)

### Optimization Features

- **Async Processing**: Concurrent Wikipedia API calls
- **Intelligent Caching**: Reduces redundant API requests
- **Fallback Strategies**: Multiple approaches for entity linking
- **Rate Limiting**: Prevents API abuse and ensures stability

## 🤝 Contributing

We welcome contributions! Please follow our development workflow for details.

### Contribution Workflow

1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Make changes** following our code quality standards
4. **Run tests**: `pytest` and quality checks: `ruff check app/`
5. **Commit changes**: Pre-commit hooks will run automatically
6. **Push branch**: `git push origin feature/amazing-feature`
7. **Create Pull Request** with detailed description

### Code Quality Requirements

- ✅ All tests must pass
- ✅ Code coverage maintained
- ✅ Ruff linting with no errors
- ✅ MyPy type checking passes
- ✅ Docstrings for all public functions
- ✅ Maximum 120 characters per line

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **API Documentation**: [Interactive Swagger UI](http://localhost:8000/docs) (when running locally)
- **Issues**: [GitHub Issues](https://github.com/janschachtschabel/entity-extractor-linker-api/issues)
- **Discussions**: [GitHub Discussions](https://github.com/janschachtschabel/entity-extractor-linker-api/discussions)

---

**Built with ❤️ using modern Python standards and production-ready architecture.**
