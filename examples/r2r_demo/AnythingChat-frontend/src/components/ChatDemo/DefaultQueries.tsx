import { Lightbulb, FlaskConical, Flame, Earth } from 'lucide-react';
import { FC } from 'react';

import { Logo } from '@/components/shared/Logo';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { DefaultQueriesProps } from '@/types';

export const DefaultQueries: FC<DefaultQueriesProps> = ({ setQuery, mode }) => {
  const defaultRagQueries = [
    {
      query: '上传文档的主要主题是什么？',
      icon: <Lightbulb className="h-6 w-6 text-yellow-400" />,
    },
    {
      query: '为我总结关键要点。',
      icon: <FlaskConical className="h-6 w-6 text-purple-400" />,
    },
    {
      query: '您在文档中发现了什么问题？',
      icon: <Flame className="h-6 w-6 text-red-400" />,
    },
    {
      query: '这些文档之间是如何相互关联的？',
      icon: <Earth className="h-6 w-6 text-green-400" />,
    },
  ];

  const defaultAgentQueries = [
    {
      query: '你好！今天过得怎么样？',
      icon: <Lightbulb className="h-6 w-6 text-yellow-400" />,
    },
    {
      query: '你能帮我更好地理解我的文档吗？',
      icon: <FlaskConical className="h-6 w-6 text-purple-400" />,
    },
    {
      query: '智能RAG从长远来看如何帮助我？',
      icon: <Flame className="h-6 w-6 text-red-400" />,
    },
    {
      query: '你能做的最酷的事情是什么？',
      icon: <Earth className="h-6 w-6 text-green-400" />,
    },
  ];

  const getQueriesBasedOnMode = (mode: 'rag' | 'rag_agent') => {
    if (mode === 'rag') {
      return defaultRagQueries;
    } else if (mode === 'rag_agent') {
      return defaultAgentQueries;
    } else {
      throw new Error('Invalid mode');
    }
  };

  const defaultQueries = getQueriesBasedOnMode(mode);

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-8">
      <Logo width={150} height={150} disableLink={true} />
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 w-full max-w-4xl px-4">
        {defaultQueries.map(({ query, icon }, index) => (
          <Alert
            key={index}
            className="cursor-pointer hover:bg-zinc-700 flex flex-col items-start p-3 h-[100px]"
            onClick={() => setQuery(query)}
          >
            <div className="mb-2">{icon}</div>
            <AlertDescription className="text-sm text-left">
              {query}
            </AlertDescription>
          </Alert>
        ))}
      </div>
    </div>
  );
};
