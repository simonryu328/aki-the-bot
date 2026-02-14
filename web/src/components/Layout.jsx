import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { App as KonstaApp, Page, Navbar, Tabbar, TabbarLink } from 'konsta/react';

export default function Layout() {
    const location = useLocation();
    const navigate = useNavigate();

    const isCalendar = location.pathname.includes('calendar');

    return (
        <KonstaApp theme="ios" dark={true}>
            <Page>
                <Navbar
                    title={isCalendar ? 'Calendar' : 'Log Entries'}
                    subtitle={isCalendar ? 'Upcoming' : 'Mission Log'}
                    className="top-0 sticky"
                    bgClassName="bg-space-dark/80 backdrop-blur-md"
                />

                <Outlet />

                <Tabbar
                    className="fixed bottom-0 left-0 right-0 z-50"
                    bgClassName="bg-space-dark/90 backdrop-blur-md border-t border-gray-800"
                >
                    <TabbarLink
                        active={!isCalendar}
                        onClick={() => navigate('/')}
                        icon={
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                            </svg>
                        }
                        label="Memories"
                    />
                    <TabbarLink
                        active={isCalendar}
                        onClick={() => navigate('/calendar')}
                        icon={
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                            </svg>
                        }
                        label="Calendar"
                    />
                </Tabbar>
            </Page>
        </KonstaApp>
    );
}
