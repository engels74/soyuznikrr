# Zondarr

Zondarr is a unified invitation and user management system for media servers (Plex, Jellyfin).

## Core Functionality

- Generate secure, time-limited invitation codes for media server access
- Manage user identities across multiple media servers from a single interface
- Support pluggable media client architecture for different server types
- Provide library-level access control (grant access to specific content libraries)
- Track invitation usage with configurable limits and expiration

## Key Concepts

- **Invitation**: Secure code with optional expiration, max uses, and duration. Links to target servers and allowed libraries.
- **Identity**: User account within Zondarr that links to accounts on multiple media servers
- **User**: A media server account linked to an Identity (one Identity can have multiple Users across servers)
- **Media Client**: Protocol-based abstraction for communicating with Plex/Jellyfin servers
- **Client Registry**: Singleton managing available media client implementations
- **Capability**: Feature flag indicating what a media client supports (create user, library access, etc.)

## Development Phases

1. **Foundation** (current): Core infrastructure, database models, media client protocol, health endpoints
2. **Jellyfin Integration**: Full Jellyfin client implementation using jellyfin-sdk
3. **Plex Integration**: Full Plex client implementation using python-plexapi
4. **Frontend**: Admin UI for managing servers, invitations, and users

## API Design

- RESTful API with OpenAPI 3.1 documentation at `/docs`
- Swagger UI at `/swagger`, Scalar at `/scalar`
- Health endpoints: `/health`, `/health/live`, `/health/ready`
- Standard error responses with correlation IDs for traceability
