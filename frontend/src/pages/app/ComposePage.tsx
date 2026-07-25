import { useNavigate } from "react-router-dom";
import { PostComposer } from "../../components/PostComposer";

export function ComposePage() {
  const navigate = useNavigate();
  return <PostComposer onCreated={(campaign) => navigate(`/app/posts/${campaign.id}`)} />;
}
