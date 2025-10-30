import React from 'react';

export default function Card({title, value}:{title:string,value:React.ReactNode}) {
  return (
    <div className="card p-5 rounded-lg shadow-sm">
      <div className="text-sm text-gray-500">{title}</div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
    </div>
  );
}
