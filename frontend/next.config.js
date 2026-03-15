/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  // Proxy API calls to backend
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*',
        },
      ],
    };
  },
};

module.exports = nextConfig;

