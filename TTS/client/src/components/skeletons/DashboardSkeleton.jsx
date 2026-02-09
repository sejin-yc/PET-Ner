import React from 'react';

const DashboardSkeleton = () => {
  return (
    <div className="grid grid-cols-12 gap-6 h-full pb-10 animate-pulse">
      {/* Header */}
      <div className="col-span-12 flex justify-between items-center bg-white p-4 rounded-xl border border-gray-200">
        <div className="h-8 w-64 bg-gray-200 rounded" />
        <div className="h-6 w-24 bg-gray-200 rounded" />
      </div>

      {/* Left: Map + Stream */}
      <div className="col-span-12 lg:col-span-8 space-y-6">
        <section className="bg-white rounded-lg border border-gray-200 overflow-hidden h-[500px] p-4">
          <div className="h-6 w-40 bg-gray-200 rounded mb-4" />
          <div className="flex-1 w-full h-[calc(100%-2rem)] bg-gray-200 rounded" />
        </section>
        <section className="bg-white rounded-lg border border-gray-200 overflow-hidden h-[400px] p-4">
          <div className="h-6 w-32 bg-gray-200 rounded mb-4" />
          <div className="w-full h-[calc(100%-2rem)] bg-gray-200 rounded" />
        </section>
      </div>

      {/* Right: Status + Controls */}
      <div className="col-span-12 lg:col-span-4 space-y-6">
        <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
          <div className="h-5 w-24 bg-gray-200 rounded" />
          <div className="h-10 bg-gray-100 rounded-lg" />
          <div className="h-2 bg-gray-100 rounded-full" />
        </section>
        <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
          <div className="h-5 w-32 bg-gray-200 rounded" />
          <div className="grid grid-cols-3 gap-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-gray-100 rounded" />
            ))}
          </div>
        </section>
        <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
          <div className="h-5 w-36 bg-gray-200 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
          <div className="flex gap-2">
            <div className="flex-1 h-10 bg-gray-100 rounded-lg" />
            <div className="h-10 w-12 bg-gray-100 rounded-lg" />
          </div>
        </section>
      </div>
    </div>
  );
};

export default DashboardSkeleton;
