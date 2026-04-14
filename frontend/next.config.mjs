/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      { source: '/api/analyze', destination: `${api}/analyze` },
      { source: '/api/results/:id', destination: `${api}/results/:id` },
      { source: '/api/badge/:owner/:repo', destination: `${api}/badge/:owner/:repo` },
    ];
  },
};
export default nextConfig;
