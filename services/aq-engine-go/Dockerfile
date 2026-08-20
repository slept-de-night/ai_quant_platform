# Stage 1: Build the Go binary
FROM golang:1.22-alpine AS builder

WORKDIR /app

COPY go.mod ./
COPY . .

# Compile optimized static binary with stripped debug symbols
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o aq-engine main.go

# Stage 2: Minimal runtime container (~15MB)
FROM alpine:3.20

RUN apk --no-cache add ca-certificates curl tzdata

WORKDIR /app

COPY --from=builder /app/aq-engine .

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=5s --start-period=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["./aq-engine"]
