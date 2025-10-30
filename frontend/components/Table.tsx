import React from 'react';

export default function Table({columns, data}:{columns:{key:string,label:string}[], data:any[]}) {
  return (
    <div className="overflow-auto bg-white rounded shadow">
      <table className="min-w-full">
        <thead className="border-b">
          <tr>
            {columns.map(c=> <th key={c.key} className="text-left p-3 text-sm text-gray-600">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {/* 关键修复：在映射之前过滤掉 null 或 undefined 的行 */}
          {data
            .filter(row => row !== null && row !== undefined) // <--- 添加过滤逻辑
            .map((row, idx)=>(
            <tr key={idx} className="border-b hover:bg-gray-50">
              {/* 这里的 row 确保是一个对象了 */}
              {columns.map(c=> <td key={c.key} className="p-3 text-sm">{String(row[c.key] ?? '')}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}