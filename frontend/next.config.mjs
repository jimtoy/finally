const isDev = process.env.NODE_ENV === 'development';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
};

// Dev-only: proxy /api to the FastAPI backend so `npm run dev` works standalone.
// In production both are served from one origin by FastAPI, so no rewrite is needed.
if (isDev) {
  nextConfig.rewrites = async () => [
    {
      source: '/api/:path*',
      destination: `${process.env.NEXT_PUBLIC_DEV_API_ORIGIN ?? 'http://localhost:8000'}/api/:path*`,
    },
  ];
}

export default nextConfig;
