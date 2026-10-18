from test_server import ServerFixture


class WishlistTests(ServerFixture):
    def wish(self,**changes):return {**dict(id='wish',title='Headphones',note='For music',category='Tech',priceKopecks=1200050,url='https://example.com/product',priority='high',status='wanted'),**changes}

    def test_wishes_persist_complete_and_do_not_spend_money(self):
        self.request('/api/wishlist','POST',self.wish());self.request('/api/wishlist','POST',self.wish())
        self.assertEqual(len(self.request()[1]['wishlist']),1)
        self.request('/api/wishlist/wish','PATCH',self.wish(status='acquired'))
        self.stop_server();self.start_server()
        result=self.request()[1]
        self.assertEqual(result['wishlist'][0]['status'],'acquired');self.assertTrue(result['wishlist'][0]['acquiredDay'])
        self.assertEqual(result['finance']['transactions'],[])
        self.request('/api/wishlist/wish','PATCH',self.wish(status='wanted',priceKopecks=None))
        self.assertIsNone(self.request()[1]['wishlist'][0]['priceKopecks'])
        self.request('/api/wishlist/wish','DELETE',{});self.assertEqual(self.request()[1]['wishlist'],[])

    def test_validation_and_private_profiles(self):
        for key,value in [('url','javascript:alert(1)'),('priceKopecks',-1),('priceKopecks',True),('status','shared'),('priority','bad')]:
            self.assertEqual(self.request('/api/wishlist','POST',self.wish(**{key:value}))[0],400)
        self.request('/api/wishlist','POST',self.wish())
        self.request('/api/auth/register','POST',dict(email='second@example.com',name='Other',password='other-password'))
        self.assertEqual(self.request()[1]['wishlist'],[])
        self.assertEqual(self.request('/api/wishlist/wish','PATCH',self.wish())[0],404)
        self.assertEqual(self.request('/api/wishlist/wish','DELETE',{})[0],404)
