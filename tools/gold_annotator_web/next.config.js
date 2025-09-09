/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: true,
  },
  async rewrites() {
    // Proxy API calls during dev/prod to FastAPI backend
    const apiBase = process.env.NEXT_PUBLIC_API_PROXY || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/:path*`,
      },
    ];
  },
  async headers() {
    // Prevent caching of HTML responses so clients always get fresh chunk hashes
    return [
      {
        source: "/proto/:path*",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Pragma", value: "no-cache" },
          { key: "Expires", value: "0" },
        ],
      },
      {
        source: "/",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Pragma", value: "no-cache" },
          { key: "Expires", value: "0" },
        ],
      },
    ];
  },

  webpack: (config) => {
    // Avoid optional native 'canvas' module on the server
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      canvas: false,
    };
    return config;
  },
}; 

module.exports = nextConfig;
