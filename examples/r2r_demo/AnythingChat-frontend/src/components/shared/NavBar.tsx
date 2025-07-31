import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useRouter } from 'next/router';
import { forwardRef, useEffect, useState, ReactNode } from 'react';

import { Logo } from '@/components/shared/Logo';
import ModernLogo from '@/components/shared/ModernLogo';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/Button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { brandingConfig } from '@/config/brandingConfig';
import { useUserContext } from '@/context/UserContext';
import { NavbarProps, NavItemsProps } from '@/types';

interface NavItemProps {
  href: string;
  children: ReactNode;
  isActive: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ href, children, isActive }) => (
  <Link
    href={href}
    className={`px-2 py-1 text-sm font-medium ${
      isActive ? 'text-accent-base' : 'text-zinc-400 hover:text-white'
    }`}
  >
    {children}
  </Link>
);

const NavItems: React.FC<NavItemsProps> = ({
  isAuthenticated,
  role,
  pathname,
}) => {
  const homeItem = {
    path: '/',
    label: '首页',
    show: brandingConfig.navbar.menuItems.home,
  };

  const commonItems = [
    {
      path: '/documents',
      label: '文档管理',
      show: brandingConfig.navbar.menuItems.documents,
    },
    {
      path: '/collections',
      label: '集合管理',
      show: brandingConfig.navbar.menuItems.collections,
    },
    {
      path: '/chat',
      label: '智能对话',
      show: brandingConfig.navbar.menuItems.chat,
    },
    {
      path: '/search',
      label: '智能搜索',
      show: brandingConfig.navbar.menuItems.search,
    },
  ];

  const adminItems = [
    {
      path: '/users',
      label: '用户管理',
      show: brandingConfig.navbar.menuItems.users,
    },
    {
      path: '/analytics',
      label: '数据分析',
      show: brandingConfig.navbar.menuItems.analytics,
    },
    {
      path: '/settings',
      label: '系统设置',
      show: brandingConfig.navbar.menuItems.settings,
    },
  ];

  const items =
    role === 'admin'
      ? [homeItem, ...commonItems, ...adminItems]
      : [...commonItems];

  if (!isAuthenticated) {
    return null;
  }

  return (
    <nav>
      <div className="flex items-center space-x-2">
        {items
          .filter((item) => item.show)
          .map((item) => (
            <NavItem
              key={item.path}
              href={item.path}
              isActive={pathname === item.path}
            >
              {item.label}
            </NavItem>
          ))}
      </div>
    </nav>
  );
};

export const Navbar = forwardRef<React.ElementRef<'nav'>, NavbarProps>(
  function Header({ className }, ref) {
    const pathname = usePathname();
    const {
      logout,
      isAuthenticated,
      authState,
      viewMode,
      setViewMode,
      isSuperUser,
    } = useUserContext();
    const router = useRouter();
    const [isSignedIn, setIsSignedIn] = useState(false);

    useEffect(() => {
      const savedAuth = localStorage.getItem('authState');
      if (savedAuth && !isAuthenticated) {
        const authData = JSON.parse(savedAuth);
      }
      setIsSignedIn(isAuthenticated);
    }, [isAuthenticated]);

    const role = viewMode === 'user' ? 'user' : authState.userRole || 'user';

    const handleLogout = async () => {
      await logout();
      router.push('/auth/login');
    };

    return (
      <nav
        ref={ref}
        className="glass-effect bg-zinc-900/80 backdrop-blur-md shadow-lg z-50 w-full border-b border-white/10"
      >
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-4">
              <Link
                href={isSuperUser() ? '/' : '/documents'}
                className="flex-shrink-0 flex items-center"
              >
                <ModernLogo size="md" />
                <span className="ml-2 text-xl font-bold gradient-text">
                  {brandingConfig.navbar.appName}
                </span>
              </Link>
              {isSignedIn && (
                <>
                  <span className="text-zinc-400">|</span>
                  <NavItems
                    isAuthenticated={isAuthenticated}
                    role={role}
                    pathname={pathname}
                  />
                </>
              )}
            </div>
            <div className="flex items-center space-x-4">
              {brandingConfig.navbar.showDocsButton && (
                <Button
                  color="primary"
                  shape="outline_wide"
                  onClick={() =>
                    window.open('https://anythingchat-docs.com', '_blank')
                  }
                >
                  文档
                </Button>
              )}

              {isSignedIn && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Avatar className="cursor-pointer">
                      <AvatarImage src="/images/default_profile.svg" />
                      <AvatarFallback></AvatarFallback>
                    </Avatar>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => router.push('/account')}
                    >
                      个人账户
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={handleLogout}
                    >
                      退出登录
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </div>
      </nav>
    );
  }
);

Navbar.displayName = 'Navbar';
