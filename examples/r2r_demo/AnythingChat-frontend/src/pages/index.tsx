import {
  FileText,
  Boxes,
  MessageCircle,
  ScanSearch,
  BarChart2,
  FileSearch,
  Users,
  Settings,
} from 'lucide-react';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';

import R2RServerCard from '@/components/ChatDemo/ServerCard';
import Layout from '@/components/Layout';
import RequestsCard from '@/components/RequestsCard';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CardContent, Card } from '@/components/ui/card';
import { brandingConfig } from '@/config/brandingConfig';
import { useUserContext } from '@/context/UserContext';

const HomePage = () => {
  const router = useRouter();
  const { isAuthenticated, isSuperUser, pipeline } = useUserContext();
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !isSuperUser()) {
      router.replace('/documents');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <Layout includeFooter>
      <main className="w-full flex flex-col container h-screen-[calc(100%-4rem)]">
        <div className="relative bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900 p-5 min-h-screen">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Left column - Alert */}
            <div className="w-full lg:w-2/3 flex flex-col gap-4">
              <Alert
                variant="default"
                className="flex flex-col modern-card animate-fade-in"
              >
                <AlertTitle className="text-lg ">
                  <div className="flex gap-2 text-xl">
                    <span className="text-gray-500 dark:text-gray-200 font-semibold">
                      欢迎使用 {brandingConfig.deploymentName} 智能对话平台！
                    </span>
                  </div>
                </AlertTitle>
                <AlertDescription>
                  <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
                    在这里，您可以找到各种工具来帮助您管理智能对话系统，
                    并直接为用户部署面向用户的应用程序。
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    <div className="flex items-start space-x-3">
                      <FileText className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">文档管理</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          上传、更新和删除文档及其元数据。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <Boxes className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">集合管理</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          管理和共享文档组，创建知识图谱。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <MessageCircle className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">智能对话</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          生成智能对话响应。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <ScanSearch className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">智能搜索</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          在您的文档和集合中进行搜索。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <Users className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">用户管理</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          跟踪用户查询、搜索结果和AI响应。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <FileSearch className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">日志记录</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          跟踪用户查询、搜索结果和AI响应。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <BarChart2 className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">数据分析</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          丰富的用户查询和交互分析洞察。
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start space-x-3">
                      <Settings className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-sm font-semibold mb-1">系统设置</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          管理您的 {brandingConfig.deploymentName} 部署
                          设置和配置。
                        </p>
                      </div>
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
              {/* Core Services Diagram */}
              <div className="flex flex-col gap-4">
                <Card className="w-full flex flex-col modern-card animate-fade-in">
                  <CardContent className="p-6">
                    <div className="flex justify-center">
                      <Image
                        src="/images/core-services.svg"
                        alt="六大核心服务模块"
                        width={800}
                        height={600}
                        className="max-w-full h-auto"
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* Right column - Cards */}
            <div className="w-full lg:w-1/3 flex flex-col gap-4">
              {/* R2R Server Cards */}
              <div className="flex flex-col gap-4 flex-grow">
                {pipeline && (
                  <R2RServerCard
                    pipeline={pipeline}
                    onStatusChange={setIsConnected}
                  />
                )}

                <div className="flex-grow">
                  <RequestsCard />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </Layout>
  );
};

export default HomePage;
