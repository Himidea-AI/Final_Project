/**
 * TransitionContext — 암전 트랜지션 네비게이션 Context
 * App.tsx 의 navigateWithTransition 을 하위 컴포넌트(useTransition())에 주입.
 * App.tsx + 추출된 보조 컴포넌트(GlobalNav 등) 가 동일 인스턴스를 공유하도록 별도 파일 분리.
 */
import { createContext, useContext } from 'react';

/** 암전 트랜지션 네비게이션 Context — 모든 하위 컴포넌트에서 사용 가능 */
export const TransitionContext = createContext<(path: string) => void>(() => {});
export const useTransition = () => useContext(TransitionContext);
